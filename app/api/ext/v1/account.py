import uuid
import time
import aiofiles

from typing import Any
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
    target_status = filter_obj.status if filter_obj.status is not None else AccountStatus.AVAILABLE
    conditions.append(model_alias.status == target_status)
    conditions.append(model_alias.user_id == user_id)
    
    # Cooldown проверка
    conditions.append(
        or_(
            model_alias.updated_at.is_(None),
            model_alias.cooldown.is_(None),
            datetime.utcnow() > (
                model_alias.updated_at + func.make_interval(0, 0, 0, 0, 0, model_alias.cooldown, 0)
            )
        )
    )
    
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
        conditions.append(model_alias.number.ilike(f"%{filter_obj.number__ilike}%"))
    
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
            conditions.append(info_attr != getattr(filter_obj, f"{info_field}__neq"))
        if getattr(filter_obj, f"{info_field}__in", None):
            conditions.append(info_attr.in_(getattr(filter_obj, f"{info_field}__in")))
        if getattr(filter_obj, f"{info_field}__ilike", None):
            conditions.append(info_attr.ilike(f"%{getattr(filter_obj, f'{info_field}__ilike')}%"))
    
    return conditions


@router.post(
    '/upload',
    response_model=schemas.Account,
    status_code=status.HTTP_201_CREATED
)
async def upload_archive(
    *,
    file: UploadFile = File(...),
    profile_file: UploadFile | None = File(None),
    session: AsyncSession = Depends(deps.get_db),
    user=Depends(deps.get_user_by_api_key),
    obj_in: schemas.AccountUpload = \
            Depends(deps.as_form(schemas.AccountUpload))
) -> Any:
    """
    Загрузка архива аккаунта.
    
    Принимает файл и все поля AccountCreate для создания записи в БД.
    """
    try:
        # Проверка расширения файла
        if not file.filename.endswith('.tar.gz'):
            logger.warning(
                f'Invalid file extension: {file.filename}',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'filename': file.filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file must have a .tar.gz extension"
            )

        # Проверка расширения файла профиля
        if profile_file and not profile_file.filename.endswith('.txt'):
            logger.warning(
                f'Invalid profile file extension: {profile_file.filename}',
                event=E.SYSTEM.API.FAILURE,
                extra={'user_id': user.id, 'filename': profile_file.filename}
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The file must have a .txt extension"
            )

        # Проверка существования аккаунта с таким же number (глобальный поиск)
        existing_account = await crud.account.get_by(
            db=session, number=obj_in.number
        )

        # Режим обновления: если аккаунт найден
        if existing_account:
            logger.info(
                'Account found by number, updating existing account',
                event=E.SYSTEM.API.REQUEST,
                extra={
                    'user_id': user.id,
                    'existing_account_id': existing_account.id,
                    'number': obj_in.number,
                    'old_uuid': str(existing_account.uuid)
                }
            )

            # Сохраняем старые имена файлов для последующего удаления
            old_file_name = existing_account.file_name
            old_profile_file_name = existing_account.profile_file_name

            # Удаление старого архива с диска (если существует)
            if old_file_name:
                old_file_path = UPLOAD_DIR / old_file_name
                if old_file_path.exists():
                    try:
                        old_file_path.unlink()
                        logger.info(
                            'Old archive file deleted successfully',
                            event=E.SYSTEM.API.REQUEST,
                            extra={
                                'user_id': user.id,
                                'file_path': str(old_file_path)
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            'Failed to delete old archive file',
                            event=E.SYSTEM.API.FAILURE,
                            extra={
                                'user_id': user.id,
                                'file_path': str(old_file_path),
                                'error': {'type': type(e).__name__, 'msg': str(e)}
                            }
                        )
                else:
                    logger.warning(
                        'Old archive file not found on disk',
                        event=E.SYSTEM.API.FAILURE,
                        extra={
                            'user_id': user.id,
                            'file_path': str(old_file_path)
                        }
                    )

            # Удаление старого файла профиля с диска (если существует)
            if old_profile_file_name:
                old_profile_path = PROFILE_UPLOAD_DIR / old_profile_file_name
                if old_profile_path.exists():
                    try:
                        old_profile_path.unlink()
                        logger.info(
                            'Old profile file deleted successfully',
                            event=E.SYSTEM.API.REQUEST,
                            extra={
                                'user_id': user.id,
                                'file_path': str(old_profile_path)
                            }
                        )
                    except Exception as e:
                        logger.warning(
                            'Failed to delete old profile file',
                            event=E.SYSTEM.API.FAILURE,
                            extra={
                                'user_id': user.id,
                                'file_path': str(old_profile_path),
                                'error': {'type': type(e).__name__, 'msg': str(e)}
                            }
                        )
                else:
                    logger.warning(
                        'Old profile file not found on disk',
                        event=E.SYSTEM.API.FAILURE,
                        extra={
                            'user_id': user.id,
                            'file_path': str(old_profile_path)
                        }
                    )

            # Генерация новых имён файлов
            timestamp = int(time.time())
            file_name = f"{obj_in.number}_{timestamp}.tar.gz"
            file_path = UPLOAD_DIR / file_name

            profile_file_name = None
            profile_file_path = None

            if profile_file:
                profile_file_name = f"{obj_in.number}_{timestamp}.txt"
                profile_file_path = PROFILE_UPLOAD_DIR / profile_file_name

            # Сохранение новых файлов
            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            if profile_file_path:
                content = await profile_file.read()
                async with aiofiles.open(profile_file_path, "wb") as f:
                    await f.write(content)

            # Генерация нового UUID
            new_uuid = uuid.uuid4()

            # Подготовка данных для обновления (полная перезапись всех полей)
            account_data = {
                'uuid': new_uuid,
                'user_id': user.id,
                'number': obj_in.number,
                'type': obj_in.type,
                'file_name': file_name,
                'profile_file_name': profile_file_name,
                'limit': obj_in.limit,
                'cooldown': obj_in.cooldown,
                'geo': obj_in.geo,
                'info_1': obj_in.info_1,
                'info_2': obj_in.info_2,
                'info_3': obj_in.info_3,
                'info_4': obj_in.info_4,
                'info_5': obj_in.info_5,
                'info_6': obj_in.info_6,
                'info_7': obj_in.info_7,
                'info_8': obj_in.info_8
            }

            # Обновление записи в БД
            account = await crud.account.update(
                db=session,
                db_obj=existing_account,
                obj_in=account_data
            )

            logger.info(
                'Account updated successfully',
                event=E.SYSTEM.API.RESPONSE,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'new_uuid': str(account.uuid),
                    'old_uuid': str(existing_account.uuid),
                    'file_name': file_name,
                    'profile_file_name': profile_file_name
                }
            )

            return schemas.Account.model_validate(account)

        # Режим создания: если аккаунт не найден
        else:
            # Генерация имени файла
            timestamp = int(time.time())
            if obj_in.number:
                file_name = f"{obj_in.number}_{timestamp}.tar.gz"
            else:
                file_name = file.filename
            
            file_path = UPLOAD_DIR / file_name

            profile_file_name = None
            profile_file_path = None

            if profile_file:
                if obj_in.number:
                    profile_file_name = f"{obj_in.number}_{timestamp}.txt"
                else:
                    profile_file_name = profile_file.filename

                profile_file_path = PROFILE_UPLOAD_DIR / profile_file_name

            logger.info(
                f'Uploading account archive',
                event=E.SYSTEM.API.REQUEST,
                extra={
                    'user_id': user.id,
                    'file_name': file_name,
                    'profile_file_name': profile_file_name,
                    'number': obj_in.number
                }
            )
            
            # Сохранение файлов
            content = await file.read()
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(content)

            if profile_file_path:
                content = await profile_file.read()
                async with aiofiles.open(profile_file_path, "wb") as f:
                    await f.write(content)
            
            # Обновляем данные для создания записи
            account_data = obj_in.model_dump(exclude_unset=True)
            account_data.update({
                'uuid': uuid.uuid4(),
                'user_id': user.id,
                'file_name': file_name,
                'profile_file_name': profile_file_name
            })
            
            # Создание записи в БД
            account = await crud.account.create(
                db=session,
                obj_in=account_data
            )
            
            logger.info(
                'Account archive uploaded successfully',
                event=E.SYSTEM.API.RESPONSE,
                extra={
                    'user_id': user.id,
                    'account_id': account.id,
                    'account_uuid': str(account.uuid),
                    'file_name': file_name
                }
            )
            
            return schemas.Account.model_validate(account)
        
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                'user_id': user.id, 'file_name': file.filename,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise e


@router.get(
    '/',
    response_model=schemas.Account,
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
            filter_conditions = _build_account_filter_conditions(filter, A, user.id)
            
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
                .where(models.Account.id == select(locked.c.id).scalar_subquery())
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
            
            # Формируем URL для скачивания
            base = (
                request.headers.get("x-base-url") or str(request.base_url)
            ).strip()
            logger.info(
                "!!!!!!!!!!!!!!!",
                event=E.SYSTEM.API.REQUEST,
                extra={
                    "x-base-url": request.headers.get("x-base-url"), "request.base_url": str(request.base_url)
                }
            )
            download_url = urljoin(
                base if base.endswith('/') else base + '/',
                f'ext/api/v1/account/{account.uuid}?x_api_key={user.ext_api_key}'
            )
            profile_download_url = urljoin(
                base if base.endswith('/') else base + '/',
                f'ext/api/v1/account/profile/{account.uuid}?x_api_key={user.ext_api_key}'
            )
            
            # Конвертируем ORM объект в схему Account с download_url
            account_dict = schemas.Account.model_validate(account).model_dump()
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
            
            return schemas.Account(**account_dict)
            
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
        account = await crud.account.get_by(db=session, uuid=uuid)
        
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
        account = await crud.account.get_by(db=session, uuid=uuid)

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
