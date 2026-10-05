import asyncio
import uuid
import time
import aiofiles

from collections.abc import Collection
from typing import Any, Literal
from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime

from fastapi import (
    Request, APIRouter, Depends, UploadFile, File, HTTPException, status
)
from fastapi.responses import FileResponse
from sqlalchemy import select, update, func, or_
from sqlalchemy.orm import aliased
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E
from app.models.account import AccountStatus
import app.models as models

import app.deps as deps
import app.crud as crud
import app.schemas as schemas
from app.services.log import log_service


UPLOAD_DIR = Path('upload/wa')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_UPLOAD_DIR = Path('upload/wa/profile')
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


def _build_account_filter_conditions(filter_obj, model_alias, user_id):
    """
    Построение WHERE условий для фильтрации аккаунтов.
    
    Обязательные условия: status, user_id, cooldown.
    Дополнительные: id, number, type, geo, info_1-info_8 с операторами.
    """
    conditions = []
    
    # Обязательные условия
    target_status = filter_obj.status \
        if filter_obj.status is not None else AccountStatus.AVAILABLE
    conditions.append(model_alias.status == target_status)
    conditions.append(model_alias.user_id == user_id)
    
    # Cooldown проверка
    conditions.append(
        or_(
            model_alias.updated_at.is_(None),
            model_alias.cooldown.is_(None),
            datetime.utcnow() > (
                model_alias.updated_at +
                func.make_interval(0, 0, 0, 0, 0, model_alias.cooldown, 0)
            )
        )
    )

    # Аккаунт должен иметь архив или hash для внешнего клиента.
    conditions.append(or_(
        model_alias.file_name.is_not(None),
        model_alias.hash.is_not(None)
    ))

    # Явный file_name фильтр дополняет обязательное условие доступности.
    if filter_obj.file_name__isnull is not None:
        if filter_obj.file_name__isnull:
            conditions.append(model_alias.file_name.is_(None))
        else:
            conditions.append(model_alias.file_name.is_not(None))
    
    # id фильтры
    if filter_obj.id is not None:
        conditions.append(model_alias.id == filter_obj.id)
    if filter_obj.id__neq is not None:
        conditions.append(model_alias.id != filter_obj.id__neq)
    if filter_obj.id__in:
        conditions.append(model_alias.id.in_(filter_obj.id__in))
    if filter_obj.id__gt is not None:
        conditions.append(model_alias.id > filter_obj.id__gt)
    if filter_obj.id__lt is not None:
        conditions.append(model_alias.id < filter_obj.id__lt)
    
    # number фильтры
    if filter_obj.number:
        conditions.append(model_alias.number == filter_obj.number)
    if filter_obj.number__neq:
        conditions.append(model_alias.number != filter_obj.number__neq)
    if filter_obj.number__in:
        conditions.append(model_alias.number.in_(filter_obj.number__in))
    if filter_obj.number__ilike:
        conditions.append(
            model_alias.number.ilike(f"%{filter_obj.number__ilike}%")
        )
    
    # type фильтры
    if filter_obj.type is not None:
        conditions.append(model_alias.type == filter_obj.type)
    if filter_obj.type__neq is not None:
        conditions.append(model_alias.type != filter_obj.type__neq)
    if filter_obj.type__in:
        conditions.append(model_alias.type.in_(filter_obj.type__in))
    
    # geo фильтры
    if filter_obj.geo:
        conditions.append(model_alias.geo == filter_obj.geo)
    if filter_obj.geo__neq:
        conditions.append(model_alias.geo != filter_obj.geo__neq)
    if filter_obj.geo__in:
        conditions.append(model_alias.geo.in_(filter_obj.geo__in))
    if filter_obj.geo__ilike:
        conditions.append(model_alias.geo.ilike(f"%{filter_obj.geo__ilike}%"))
    
    # info_1 - info_8 фильтры
    for i in range(1, 9):
        info_field = f"info_{i}"
        info_attr = getattr(model_alias, info_field)
        
        if getattr(filter_obj, info_field, None):
            conditions.append(info_attr == getattr(filter_obj, info_field))
        if getattr(filter_obj, f"{info_field}__neq", None):
            conditions.append(
                info_attr != getattr(filter_obj, f"{info_field}__neq")
            )
        if getattr(filter_obj, f"{info_field}__in", None):
            conditions.append(
                info_attr.in_(getattr(filter_obj, f"{info_field}__in"))
            )
        if getattr(filter_obj, f"{info_field}__ilike", None):
            conditions.append(info_attr.ilike(
                f"%{getattr(filter_obj, f'{info_field}__ilike')}%")
            )
    
    return conditions


def _apply_upload_hash(
    account_data: dict[str, Any], obj_in: schemas.AccountUpload
) -> None:
    """Добавляет только явно переданный непустой hash загрузки."""
    if 'hash' in obj_in.model_fields_set and obj_in.hash:
        account_data['hash'] = obj_in.hash


def _prepare_upload_data(
    obj_in: schemas.AccountUpload,
    *,
    provided_fields: Collection[str],
    user_id: int,
    account_uuid: uuid.UUID,
    file_name: str,
    profile_file_name: str | None,
    is_update: bool,
) -> dict[str, Any]:
    """Preserve omitted required values without changing nullable semantics."""
    if "type" in provided_fields and obj_in.type is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The type field cannot be empty",
        )

    data = obj_in.model_dump(exclude_unset=not is_update, exclude={"hash"})
    if "type" not in provided_fields:
        data.pop("type", None)
    _apply_upload_hash(data, obj_in)
    data.update({
        "uuid": account_uuid,
        "user_id": user_id,
        "file_name": file_name,
        "profile_file_name": profile_file_name,
    })
    return data


async def _save_upload_file(file: UploadFile, file_path: Path) -> None:
    """Write and close a new upload without removing existing artifacts."""
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as destination:
        await destination.write(content)


def _account_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Account not found'
    )


async def _find_owned_account(
    session: AsyncSession,
    *,
    user_id: int,
    account_id: int | None = None,
    number: str | None = None
) -> models.Account:
    """Находит единственный аккаунт владельца по ID или номеру."""
    if account_id is not None:
        account = await crud.account.get_owned_by_id(
            session, account_id=account_id, user_id=user_id
        )
        if account is None:
            raise _account_not_found()
        return account

    matches = await crud.account.list_owned_by_number(
        session, number=number, user_id=user_id
    )
    if not matches:
        raise _account_not_found()
    if len(matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Multiple accounts found for number'
        )
    return matches[0]


async def _set_account_hash(
    session: AsyncSession,
    *,
    account: models.Account,
    user_id: int,
    value: str | None
) -> models.Account:
    """Изменяет hash, освобождает аккаунт и сохраняет аудит."""
    updated_account = await crud.account.update_hash(
        session,
        account_id=account.id,
        user_id=user_id,
        value=value,
        commit=False
    )
    if updated_account is None:
        raise _account_not_found()

    await log_service.record(
        session,
        event='account.update',
        source='ext_api',
        account_id=updated_account.id,
        user_id=user_id,
        status=updated_account.status,
        commit=False
    )
    await session.commit()

    logger.info(
        'Account hash updated successfully',
        event=E.SYSTEM.API.RESPONSE,
        extra={'user_id': user_id, 'account_id': updated_account.id}
    )
    return updated_account


@router.post(
    '/upload',
    response_model=schemas.AccountExternal,
    status_code=status.HTTP_201_CREATED
)
async def upload_archive(
    *,
    request: Request,
    file: UploadFile = File(...),
    profile_file: UploadFile | None = File(None),
    session: AsyncSession = Depends(deps.get_db),
    user: models.User = Depends(deps.get_user_by_api_key),
    obj_in: schemas.AccountUpload = Depends(
        deps.as_form(schemas.AccountUpload)
    ),
) -> schemas.AccountExternal:
    """
    Загрузить архив .tar.gz и необязательный профиль .txt по API Key.

    Создаёт аккаунт либо обновляет найденный по number и user_id
    аутентифицированного пользователя. Например, multipart с
    number=100, type=2 и file=account.tar.gz возвращает AccountExternal (201).
    Зависимости предоставляют сессию БД, пользователя и поля AccountUpload.
    Файловый I/O выполняется между короткими транзакциями. Старые файлы
    удаляются только после подтверждённого commit и проверки ссылок на них.
    Ошибки cleanup журналируются независимо и не отменяют успешную загрузку.
    """
    actor_id = user.id
    audit = log_service.operation(action="account.upload", user_id=actor_id)
    before: dict[str, Any] | None = None
    requested: dict[str, Any] | None = None
    returned: dict[str, Any] | None = None
    branch: Literal["create", "update"] | None = None
    provided_fields: set[str] = set()
    files_written: list[str] = []

    def audit_details(cleanup: dict[str, Any] | None = None) -> dict[str, Any]:
        return log_service.upload_details(
            request=request, obj_in=obj_in, provided_fields=provided_fields,
            file=file, profile_file=profile_file, branch=branch,
            before=before, requested=requested, returned=returned,
            files_written=files_written, archive_directory=UPLOAD_DIR,
            profile_directory=PROFILE_UPLOAD_DIR, cleanup=cleanup,
        )

    try:
        provided_fields = set((await request.form()).keys())
        response_user = schemas.User.model_validate(user)
        archive_filename = file.filename or ""
        profile_filename = (
            (profile_file.filename or "") if profile_file else ""
        )
        if not archive_filename.endswith('.tar.gz'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file must have a .tar.gz extension"
            )
        if profile_file and not profile_filename.endswith('.txt'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file must have a .txt extension"
            )

        audit.stage = "lookup"
        await session.begin()
        before = await crud.account.get_upload_snapshot(
            db=session, number=obj_in.number, user_id=actor_id
        )
        if before is not None:
            audit.account_id = before["id"]
        await session.commit()
        branch = "update" if before is not None else "create"

        audit.stage = "validate"
        timestamp = int(time.time())
        numbered_name = before is not None or bool(obj_in.number)
        file_name = (
            f"{obj_in.number}_{timestamp}.tar.gz" if numbered_name
            else archive_filename
        )
        profile_file_name = None
        if profile_file:
            profile_file_name = (
                f"{obj_in.number}_{timestamp}.txt" if numbered_name
                else profile_filename
            )
        account_data = _prepare_upload_data(
            obj_in,
            provided_fields=provided_fields,
            user_id=actor_id,
            account_uuid=uuid.uuid4(),
            file_name=file_name,
            profile_file_name=profile_file_name,
            is_update=before is not None,
        )
        requested = dict(account_data)
        if before is not None:
            requested["id"] = before["id"]

        audit.stage = "write_archive"
        await _save_upload_file(file, UPLOAD_DIR / file_name)
        files_written.append("archive")
        if profile_file is not None and profile_file_name is not None:
            audit.stage = "write_profile"
            await _save_upload_file(
                profile_file, PROFILE_UPLOAD_DIR / profile_file_name
            )
            files_written.append("profile")

        audit.stage = "db_write"
        await session.begin()
        if before is not None:
            account = await crud.account.update(
                db=session,
                id=before["id"],
                obj_in=account_data,
                commit=False,
                returning="object",
            )
        else:
            account = await crud.account.create(
                db=session, obj_in=account_data, commit=False,
            )

        audit.stage = "verify_returning"
        account_values = vars(account) if account is not None else None
        returned = log_service.upload_snapshot(account_values)
        if (
            account_values is None or account_values.get("id") is None
            or (before is not None and account_values["id"] != before["id"])
            or account_values.get("file_name") != file_name
            or "profile_file_name" not in account_values
            or account_values.get("profile_file_name") != profile_file_name
            or account_values.get("user_id") != actor_id
        ):
            raise RuntimeError("Account upload RETURNING verification failed")
        if before is None:
            audit.new_account_id = account_values["id"]

        audit.stage = "audit"
        await log_service.record(
            session,
            event=f"account.{branch}",
            source="ext_api",
            account_id=account_values["id"],
            user_id=actor_id,
            status=account_values.get("status"),
            commit=False,
        )
        audit.stage = "prepare_response"
        response = schemas.AccountExternal.model_validate({
            **account_values, "user": response_user,
        })
        audit.stage = "commit"
        audit.db_outcome = "unknown"
        await session.commit()
        audit.db_outcome = "committed"
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            session, error, operation=audit, details=audit_details,
        )
        raise

    audit.stage = "cleanup"
    for kind, column, directory, profile in (
        ("archive", "file_name", UPLOAD_DIR, False),
        ("profile", "profile_file_name", PROFILE_UPLOAD_DIR, True),
    ):
        old_name = before.get(column) if before is not None else None
        if not old_name:
            continue
        cleanup = {
            "kind": kind, "file_name": old_name,
            "path": directory / old_name, "action": "reference_check",
        }
        try:
            await session.begin()
            referenced = await crud.account.is_file_referenced(
                db=session, file_name=old_name, profile=profile,
            )
            await session.commit()
            if not referenced:
                cleanup["action"] = "delete"
                await asyncio.to_thread(
                    (directory / old_name).unlink, missing_ok=True,
                )
        except (Exception, asyncio.CancelledError) as error:
            released = await log_service.report_error(
                session, error, operation=audit,
                details=lambda: audit_details(cleanup),
            )
            if isinstance(error, asyncio.CancelledError):
                raise
            if not released:
                break

    if not audit.release_failed and not session.in_transaction():
        audit.stage = "success_log"
        try:
            await asyncio.to_thread(
                logger.info,
                "Account updated successfully" if before is not None
                else "Account archive uploaded successfully",
                event=E.SYSTEM.API.RESPONSE,
                extra={
                    "user_id": actor_id,
                    "account_id": response.id,
                    "account_uuid": log_service.safe_value(response.uuid),
                    "old_uuid": log_service.safe_value(
                        before.get("uuid") if before is not None else None
                    ),
                    "file_name": log_service.safe_value(response.file_name),
                    "profile_file_name": log_service.safe_value(
                        response.profile_file_name
                    ),
                },
            )
        except (Exception, asyncio.CancelledError) as error:
            await log_service.report_error(
                session, error, operation=audit, details=audit_details,
            )
            if isinstance(error, asyncio.CancelledError):
                raise
    return response


@router.post(
    '/hash',
    response_model=schemas.AccountHashUpdateResponse,
    status_code=status.HTTP_200_OK
)
async def update_account_hash_by_locator(
    *,
    obj_in: schemas.AccountHashLookupUpdate,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_user_by_api_key)
) -> schemas.AccountHashUpdateResponse:
    """Устанавливает или очищает hash аккаунта владельца по ID или номеру."""
    try:
        account = await _find_owned_account(
            session,
            user_id=user.id,
            account_id=obj_in.id,
            number=obj_in.number
        )
        updated_account = await _set_account_hash(
            session, account=account, user_id=user.id, value=obj_in.hash
        )
        return schemas.AccountHashUpdateResponse.model_validate(
            updated_account
        )
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        logger.exception(
            event=E.SYSTEM.API.ERROR,
            extra={
                'user_id': user.id,
                'account_id': obj_in.id,
                'number': obj_in.number,
                'error': {'type': type(exc).__name__, 'msg': str(exc)}
            }
        )
        raise


@router.post(
    '/{id}/hash',
    response_model=schemas.AccountHashUpdateResponse,
    status_code=status.HTTP_200_OK
)
async def update_account_hash_by_id(
    *,
    id: int,
    obj_in: schemas.AccountHashUpdate,
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_user_by_api_key)
) -> schemas.AccountHashUpdateResponse:
    """Устанавливает или очищает hash аккаунта владельца по ID пути."""
    try:
        account = await _find_owned_account(
            session, user_id=user.id, account_id=id
        )
        updated_account = await _set_account_hash(
            session, account=account, user_id=user.id, value=obj_in.hash
        )
        return schemas.AccountHashUpdateResponse.model_validate(
            updated_account
        )
    except HTTPException:
        raise
    except Exception as exc:
        await session.rollback()
        logger.exception(
            event=E.SYSTEM.API.ERROR,
            extra={
                'user_id': user.id,
                'account_id': id,
                'error': {'type': type(exc).__name__, 'msg': str(exc)}
            }
        )
        raise


@router.get(
    '/',
    response_model=schemas.AccountExternalWithHash,
    status_code=status.HTTP_200_OK
)
async def get_account(
    *,
    session: AsyncSession = Depends(deps.get_db),
    filter: schemas.AccountFilter = Depends(),
    user=Depends(deps.get_user_by_api_key),
    request: Request
) -> Any:
    """
    Получить аккаунт по фильтрам.

    Возвращает первый найденный аккаунт со ссылкой на скачивание архива.
    Использует атомарную блокировку (FOR UPDATE SKIP LOCKED) и автоматически
    меняет статус на ACTIVE.
    """
    try:
        async with session.begin():
            # Создаем alias для модели Account
            A = aliased(models.Account)

            # Строим список WHERE условий с учетом всех фильтров
            filter_conditions = \
                _build_account_filter_conditions(filter, A, user.id)
            
            # Создаем CTE для блокировки аккаунта
            locked = (
                select(A.id)
                .where(*filter_conditions)
                .order_by(A.updated_at.asc().nullsfirst(), A.id.asc())
                .limit(1)
                .with_for_update(skip_locked=True)
                .cte('locked')
            )
            
            # Обновляем статус на ACTIVE с использованием RETURNING
            statement = (
                update(models.Account)
                .where(
                    models.Account.id == select(locked.c.id).scalar_subquery()
                )
                .values(status=AccountStatus.ACTIVE)
                .returning(models.Account)
            )
            
            row = (await session.execute(statement)).first()
            
            if row is None:
                logger.warning(
                    'Account not found',
                    event=E.SYSTEM.API.NOT_FOUND,
                    extra={'user_id': user.id, 'filter': filter.model_dump()}
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail='Account not found'
                )
            
            account = row[0]

            await log_service.record(
                session,
                event="account.status",
                source="ext_api",
                account_id=account.id,
                user_id=user.id,
                status=account.status,
                commit=False
            )
            
            # Формируем URL для скачивания
            base = (
                request.headers.get("x-base-url") or str(request.base_url)
            ).strip()
            download_url = urljoin(
                base if base.endswith('/') else base + '/',
                f'ext/api/v1/account/{account.uuid}?x_api_key={user.ext_api_key}'
            )
            profile_download_url = urljoin(
                base if base.endswith('/') else base + '/',
                f'ext/api/v1/account/profile/{account.uuid}?x_api_key={user.ext_api_key}'
            )
            
            # Конвертируем ORM объект в схему Account с download_url
            account_dict = schemas.AccountExternalWithHash.model_validate(
                account
            ).model_dump()
            if account.file_name:
                account_dict['download_url'] = download_url
            if account.profile_file_name:
                account_dict['profile_download_url'] = profile_download_url
            
            logger.info(
                'Account retrieved successfully',
                event=E.SYSTEM.API.RESPONSE,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'account_uuid': str(account.uuid)
                }
            )
            
            return schemas.AccountExternalWithHash(**account_dict)
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise e


@router.get("/{uuid}")
async def download_archive(
    *,
    session: AsyncSession = Depends(deps.get_db),
    uuid: str,
    user=Depends(deps.get_user_by_api_key)
):
    """
    Скачивание архива аккаунта по UUID.
    """
    try:
        account = await crud.account.get_by(
            db=session, uuid=uuid, user_id=user.id
        )
        
        if not account:
            logger.warning(
                f'Archive not found by UUID',
                event=E.SYSTEM.API.NOT_FOUND,
                extra={'user_id': user.id, 'uuid': uuid}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Archive with UUID={uuid} not found'
            )
        
        if not account.file_name:
            logger.warning(
                'Archive filename not specified',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'account_id': account.id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Archive filename not specified'
            )
        
        file_path = UPLOAD_DIR / account.file_name
        
        if not file_path.exists():
            logger.error(
                f'Archive file not found on disk',
                event=E.SYSTEM.API.ERROR,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'file_path': str(file_path)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'File {file_path} not found'
            )
        
        logger.info(
            'Archive download initiated',
            event=E.SYSTEM.API.RESPONSE,
            extra={
                'user_id': user.id,
                'account_id': account.id,
                'file_name': account.file_name
            }
        )
        
        return FileResponse(
            path=file_path,
            filename=account.file_name,
            media_type='application/gzip'
        )
        
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id, 'uuid': uuid,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise e


@router.get("/profile/{uuid}")
async def download_archive(
    *,
    session: AsyncSession = Depends(deps.get_db),
    uuid: str,
    user=Depends(deps.get_user_by_api_key)
):
    """
    Скачивание текстового файла профиля по UUID.
    """
    try:
        account = await crud.account.get_by(
            db=session, uuid=uuid, user_id=user.id
        )

        if not account:
            logger.warning(
                f'Profile not found by UUID',
                event=E.SYSTEM.API.NOT_FOUND,
                extra={'user_id': user.id, 'uuid': uuid}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Profile with UUID={uuid} not found'
            )

        if not account.profile_file_name:
            logger.warning(
                'Profile filename not specified',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'account_id': account.id}
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Profile filename not specified'
            )

        file_path = PROFILE_UPLOAD_DIR / account.profile_file_name

        if not file_path.exists():
            logger.error(
                f'Profile file not found on disk',
                event=E.SYSTEM.API.ERROR,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'file_path': str(file_path)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'File {file_path} not found'
            )

        logger.info(
            'Profile download initiated',
            event=E.SYSTEM.API.RESPONSE,
            extra={
                'user_id': user.id,
                'account_id': account.id,
                'file_name': account.profile_file_name
            }
        )

        return FileResponse(
            path=file_path,
            filename=account.profile_file_name,
            media_type='application/gzip'
        )

    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id, 'uuid': uuid,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise e
