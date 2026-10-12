"""
Маршруты API для работы с аккаунтами.

Функциональность
----------------
- Получение списка аккаунтов с фильтрацией, сортировкой и пагинацией
  (через fastapi-filter). Если параметр сортировки `order_by` не передан,
  применяется значение по умолчанию: `-id` (по убыванию).
- Создание, чтение, обновление и удаление аккаунта.
- Поиск аккаунтов с указанным, но отсутствующим на диске архивом.

Безопасность
------------
Операции с записями требуют авторизованного активного пользователя
(`deps.get_current_active_user`). Standalone-файлы доступны без JWT.
Поиск отсутствующих архивов доступен только superuser.

Зависимости
-----------
- SQLAlchemy AsyncSession (`deps.get_db`)
- fastapi-filter (`FilterDepends(schemas.AccountFilter)`)

Примеры сортировки
------------------
- По одному полю (ASC):   `GET /accounts?order_by=id`
- По одному полю (DESC):  `GET /accounts?order_by=-created_at`
- По двум полям:          `GET /accounts?order_by=status&order_by=-id`

Примеры фильтров
----------------
По текстовому полю `number`:
- Равенство (eq):         `GET /accounts?number=12345`
- Вхождение (in):         `GET /accounts?number__in=100,200,300`
- Подстрока (like/ilike): `GET /accounts?number__like=%123%`
                          `GET /accounts?number__ilike=%123%`
  Примечание: для `ilike` в фильтре должен быть определён атрибут
  `number__ilike: str | None = None`. В значении используются SQL-шаблоны
  (`%` — любой набор символов, `_` — один символ).

Другие примеры:
- По пользователю:        `GET /accounts?user_id=42`
- По статусам:            `GET /accounts?status__in=1,2`
- По дате создания:       `GET /accounts?created_at__gte=2025-09-01T00:00:00Z`
"""

import asyncio
import uuid, shutil  # noqa

from typing import Any, List, Dict, Sequence, cast
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter, Query, Depends, Request,
    UploadFile, File, HTTPException, status
)

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E
from app.crud.filter.base import FilterDepends
from app.models.account import AccountStatus

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas
from app.services.log import LogOperation, log_service
from app.utils.account_files import account_file_exists as _account_file_exists


UPLOAD_DIR = Path('upload/wa')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_UPLOAD_DIR = Path('upload/wa/profile')
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

_ACCOUNT_FILE_SCAN_BATCH_SIZE = 1000


router = APIRouter()


def _missing_account_file_ids(
    directory: Path, archive_files: Sequence[tuple[int, str]]
) -> list[int]:
    """Проверяет порцию архивов, не скрывая недоступность хранилища."""
    if not directory.is_dir():
        raise NotADirectoryError(
            f"Account archive directory is unavailable: {directory}"
        )
    return [
        account_id for account_id, file_name in archive_files
        if file_name and not _account_file_exists(directory, file_name)
    ]


def _delivery_summary(
    delivered: int,
    terminal: int
) -> schemas.AccountReportDelivery:
    """Формирует процент доставки по финальным статусам сообщений."""
    return schemas.AccountReportDelivery(
        delivered=delivered,
        terminal=terminal,
        rate=round(delivered / terminal * 100, 2) if terminal else None
    )


def _account_target(
    account: models.Account | schemas.Account, *,
    requested_id: int | None = None, request_index: int | None = None,
) -> dict[str, Any]:
    """Copy allowed scalars before deletion/rollback expires ORM objects."""
    target: dict[str, Any] = {
        "account_id": account.id,
        "uuid": log_service.safe_value(account.uuid),
        "owner_user_id": account.user_id,
        "status": account.status,
    }
    if requested_id is not None:
        target["requested_account_id"] = requested_id
    if request_index is not None:
        target["request_index"] = request_index
    return target


def _unlink_account_file(path: Path) -> bool:
    """Keep the existing exists/unlink policy; a missing file is a skip."""
    if not path.exists():
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


def _write_archive(file: UploadFile, path: Path) -> None:
    with path.open('wb') as buffer:
        shutil.copyfileobj(file.file, buffer)


async def delete_account_files(
    account: schemas.Account, *, operation: LogOperation,
    details: dict[str, Any],
) -> Dict[str, Any]:
    """Queue file facts without DB access or transaction release."""
    result: Dict[str, Any] = {"deleted_files": [], "errors": []}
    for kind, directory, filename in (
        ("archive", UPLOAD_DIR, account.file_name),
        ("profile", PROFILE_UPLOAD_DIR, account.profile_file_name),
    ):
        if not filename:
            continue
        details.update(
            file_kind=kind, file_name=filename, reason="account_delete",
        )
        file_details = dict(details)
        operation.stage = f"delete_{kind}"
        operation.persist_error = kind == "archive"
        operation.error_event = (
            "account.file.delete.error" if kind == "archive" else None
        )
        try:
            deleted = await asyncio.to_thread(
                _unlink_account_file, directory / filename,
            )
        except Exception as error:
            log_service.queue_event(
                operation, event=operation.error_event,
                details=file_details, error=error,
            )
            result["errors"].append({"type": type(error).__name__})
            continue
        if not deleted:
            continue
        result["deleted_files"].append(str(directory / filename))
        if kind == "archive":
            log_service.queue_event(
                operation, event="account.file.delete", details=file_details,
            )
        # An error after unlink is not a failed unlink. Preserve the helper's
        # nonfatal logger handling, but keep profile diagnostics DB-free.
        operation.stage = f"log_{kind}_delete"
        operation.error_event = None
        try:
            await asyncio.to_thread(
                logger.info, f"Deleted {kind} file",
                event=E.SYSTEM.APP.SUCCESS, extra=file_details,
            )
        except Exception as error:
            log_service.queue_event(
                operation,
                event="account.error" if kind == "archive" else None,
                details=file_details, error=error,
            )
            result["errors"].append({"type": type(error).__name__})
    operation.persist_error = True
    operation.error_event = None
    for name in ("file_kind", "file_name", "reason"):
        details.pop(name, None)
    return result


@router.get('/', response_model=schemas.AccountList)
async def read_accounts(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.AccountFilter = FilterDepends(
        schemas.AccountFilter, as_query=True
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Возвращает список аккаунтов с поддержкой фильтрации,
    сортировки и пагинации.

    Если параметр сортировки `order_by` не указан, применяется сортировка
    по умолчанию: `-id` (DESC).

    Args:
        db: Асинхронная сессия базы данных.
        f: Фильтр `AccountFilter` (query-параметров через fastapi-filter).
        skip: Смещение (offset) для пагинации.
        limit: Максимальное число записей (limit) для пагинации.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.AccountList` вида:
        `{"data": [schemas.Account, ...], "total": <int>}` —
        где каждый аккаунт содержит device последней активной сессии,
        а `total` учитывает применённый фильтр.

    Примеры:
        - `GET /accounts?status__in=1,2&order_by=-id`
        - `GET /accounts?user_id=42&order_by=created_at&order_by=-id`
    """
    operation = log_service.operation(
        action="account.list", user_id=current_user.id, source="api",
    )
    try:
        operation.stage = "lookup"
        if not current_user.is_superuser:
            f.user_id = current_user.id
        if not getattr(f, "order_by", None):
            f.order_by = ["-id"]
        account_rows = await crud.account.list_with_active_session_device(
            db, filter=f, skip=skip, limit=limit
        )
        operation.stage = "count"
        count = await crud.account.count(db, filter=f)

        operation.stage = "prepare_response"
        now = datetime.now(timezone.utc)
        data = []
        for item, device in account_rows:
            setattr(item, "device", device)
            if (
                item.cooldown is not None and item.updated_at is not None
                and item.updated_at + timedelta(minutes=item.cooldown) > now
                and item.status == AccountStatus.AVAILABLE
            ):
                item.status = AccountStatus.PAUSED
            data.append(item)

        return {'data': data, 'total': count}
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(db, error, operation=operation)
        raise


@router.get(
    '/missing-files',
    response_model=schemas.AccountList,
    responses={
        403: {"description": "Требуются права superuser"},
        503: {"description": "Не удалось проверить хранилище архивов"}
    }
)
async def read_accounts_with_missing_files(
    db: AsyncSession = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> schemas.AccountList:
    """
    Находит аккаунты всех с отсутствующими архивами.

    Требуется Bearer JWT активного пользователя с is_superuser=True.
    Проверяется только file_name относительно UPLOAD_DIR; NULL и пустые
    имена исключаются. Каталоги и пути вне UPLOAD_DIR не считаются архивами.
    Файлы профилей не проверяются. Записи, статусы и файлы не изменяются

    Пример: GET /api/v1/accounts/missing-files?skip=0&limit=100
    """
    operation = log_service.operation(
        action="account.missing_files", user_id=current_user.id, source="api",
    )
    try:
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The user doesn't have enough privileges"
            )
        total = 0
        page_ids: list[int] = []
        before_id = None
        while True:
            operation.stage = "lookup"
            archive_files = await crud.account.list_archive_files(
                db, before_id=before_id, limit=_ACCOUNT_FILE_SCAN_BATCH_SIZE
            )
            if not archive_files:
                break

            try:
                operation.stage = "check_archive"
                missing_ids = await asyncio.to_thread(
                    _missing_account_file_ids, UPLOAD_DIR, archive_files
                )
            except (OSError, RuntimeError) as exc:
                # Path.resolve() raises RuntimeError for symlink loops in 3.11.
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Account archive storage could not be checked"
                ) from exc
            for account_id in missing_ids:
                if skip <= total < skip + limit:
                    page_ids.append(account_id)
                total += 1

            before_id = archive_files[-1][0]
            if len(archive_files) < _ACCOUNT_FILE_SCAN_BATCH_SIZE:
                break

        data = []
        if page_ids:
            operation.stage = "lookup_page"
            account_rows = await crud.account.list_with_active_session_device(
                db,
                filter=schemas.AccountFilter(
                    id__in=page_ids, order_by=["-id"]
                ),
                limit=len(page_ids)
            )
            operation.stage = "prepare_response"
            for item, device in account_rows:
                account = schemas.Account.model_validate(item)
                account.device = device
                data.append(account)

        return schemas.AccountList(data=data, total=total)
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(db, error, operation=operation)
        raise


@router.post(
    '/', status_code=status.HTTP_201_CREATED
)
async def create_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AccountMultiCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Создаёт аккаунты по списку имён ранее загруженных архивов.

    Записи и события account.create фиксируются одной транзакцией.

    Args:
        db: Асинхронная сессия базы данных.
        obj_in: Данные для создания аккаунта (`schemas.AccountCreate`).
        current_user: Текущий активный пользователь.

    Returns:
        Количество созданных аккаунтов (HTTP 201).
    """
    operation = log_service.operation(
        action="account.create", user_id=current_user.id, source="api",
    )
    request_details: dict[str, Any] = {"file_names": list(obj_in.files)}
    details = request_details
    try:
        base_data = {
            **obj_in.model_dump(
                exclude={
                    "files", "uuid", "user_id", "file_name", "session_count"
                }
            ),
            "user_id": operation.user_id,
        }
        obj_list = []
        for index, file_name in enumerate(obj_in.files):
            details = {
                "target": {"request_index": index}, "file_name": file_name,
            }
            obj_list.append(schemas.AccountCreate(
                **base_data, uuid=str(uuid.uuid4()), file_name=file_name
            ))
        details = request_details
        operation.stage = "db_write"
        accounts = await crud.account.insert(
            db=db, obj_list=obj_list, returning=True, commit=False
        )
        operation.stage = "audit_success"
        items = []
        for index, account in enumerate(accounts):
            details = {"target": {"request_index": index}}
            details["target"].update(_account_target(account))
            items.append(schemas.LogCreate(
                event="account.create", source="api", account_id=account.id,
                user_id=operation.user_id, status=account.status,
                context=log_service.operation_context(
                    operation, details=details,
                ),
            ))
        details = request_details
        await log_service.records(db, items=items, commit=False)
        operation.stage = "commit"
        operation.db_outcome = "unknown"
        await db.commit()
        operation.db_outcome = "committed"
        operation.stage = "prepare_response"
        return {"count": len(accounts)}
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise


@router.put('/{id}', response_model=schemas.Account)
async def update_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    obj_in: schemas.AccountUpdate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Обновляет данные аккаунта по идентификатору.

    Возвращает 404, если аккаунт не найден.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        obj_in: Данные для обновления (`schemas.AccountUpdate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Обновлённый объект `schemas.Account`.
    """
    operation = log_service.operation(
        action="account.update", user_id=current_user.id, source="api",
    )
    details = {"target": {"requested_account_id": id}}
    try:
        operation.stage = "lookup"
        db_obj = await crud.account.get(db=db, id=id)
        if not db_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )
        details = {"target": _account_target(db_obj, requested_id=id)}
        operation.account_id = db_obj.id
        event = "account.status" if "status" in obj_in.model_dump(
            exclude_unset=True
        ) else "account.update"
        operation.stage = "db_write"
        account = await crud.account.update(
            db=db, db_obj=db_obj, obj_in=obj_in, commit=False
        )
        operation.stage = "audit_success"
        await log_service.record(
            db,
            event=event,
            source="api",
            account_id=account.id,
            user_id=operation.user_id,
            status=account.status,
            context=log_service.operation_context(
                operation,
                details={"target": _account_target(account, requested_id=id)},
            ),
            commit=False
        )
        operation.stage = "commit"
        operation.db_outcome = "unknown"
        await db.commit()
        operation.db_outcome = "committed"
        return account
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise


@router.get('/{id}/summary', response_model=schemas.AccountReportSummary)
async def read_account_summary(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> schemas.AccountReportSummary:
    """Возвращает Overview, device активной сессии и агрегаты аккаунта."""
    operation = log_service.operation(
        action="account.summary", user_id=current_user.id, source="api",
    )
    details = {"target": {"requested_account_id": id}}
    try:
        operation.stage = "lookup"
        result = await crud.account.get_report_summary(
            db,
            account_id=id,
            owner_user_id=(
                None if current_user.is_superuser else current_user.id
            )
        )
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )

        account, stats = result
        details = {"target": _account_target(account, requested_id=id)}
        operation.account_id = account.id
        operation.stage = "prepare_response"
        now = datetime.now(timezone.utc)
        account_status = int(account.status)
        cooldown_until = None
        if account.cooldown is not None and account.updated_at is not None:
            cooldown_until = account.updated_at + timedelta(
                minutes=account.cooldown
            )
            if (
                account_status == AccountStatus.AVAILABLE
                and cooldown_until > now
            ):
                account_status = int(AccountStatus.PAUSED)

        failures: list[tuple[str, BaseException]] = []

        async def check_file(
            kind: str, directory: Path, name: str | None,
        ) -> bool:
            try:
                return await asyncio.to_thread(
                    _account_file_exists, directory, name,
                )
            except (Exception, asyncio.CancelledError) as error:
                failures.append((kind, error))
                raise

        def queue_failure(kind: str, error: BaseException) -> None:
            operation.stage = f"check_{kind}"
            log_service.queue_event(
                operation,
                event="account.error" if kind == "archive" else None,
                details=details, error=error, account_id=operation.account_id,
            )

        operation.stage = "check_files"
        try:
            archive_exists, profile_exists = await asyncio.gather(
                check_file("archive", UPLOAD_DIR, account.file_name),
                check_file(
                    "profile", PROFILE_UPLOAD_DIR, account.profile_file_name,
                ),
                return_exceptions=True,
            )
        except asyncio.CancelledError:
            # gather cancellation bypasses its result processing. Retain
            # observed errors and classify the still-pending check before
            # the outer finalizer drains facts and propagates cancellation.
            cancelled_kinds = set()
            for kind, error in failures:
                if isinstance(error, asyncio.CancelledError):
                    cancelled_kinds.add(kind)
                else:
                    queue_failure(kind, error)
            operation.persist_error = (
                not failures or "archive" in cancelled_kinds
            )
            operation.stage = (
                "check_archive" if "archive" in cancelled_kinds else
                "check_profile" if "profile" in cancelled_kinds else
                "check_files"
            )
            raise
        if failures:
            # Retain the first exception, while identifying each concurrent
            # failure by its task, never by an exception message/path.
            for kind, error in failures[1:]:
                queue_failure(kind, error)
            kind, error = failures[0]
            operation.stage = f"check_{kind}"
            operation.persist_error = kind == "archive"
            raise error

        operation.persist_error = True
        operation.stage = "prepare_response"
        return schemas.AccountReportSummary(
            account=schemas.AccountReportOverview(
                id=account.id,
                uuid=uuid.UUID(str(account.uuid)) if account.uuid else None,
                number=account.number,
                status=account_status,
                cooldown=account.cooldown,
                cooldown_until=cooldown_until,
                owner=schemas.AccountReportOwner(
                    id=account.user.id,
                    name=account.user.name
                ),
                archive=schemas.AccountReportFile(
                    name=account.file_name,
                    exists=cast(bool, archive_exists)
                ),
                profile=schemas.AccountReportFile(
                    name=account.profile_file_name,
                    exists=cast(bool, profile_exists)
                )
            ),
            session_count=int(stats["session_count"] or 0),
            current_session_id=stats["current_session_id"],
            device=stats["device"],
            message_count_current=int(stats["message_count_current"] or 0),
            message_count_total=int(stats["message_count_total"] or 0),
            delivery_current=_delivery_summary(
                int(stats["delivery_current_delivered"] or 0),
                int(stats["delivery_current_terminal"] or 0)
            ),
            delivery_all_time=_delivery_summary(
                int(stats["delivery_all_delivered"] or 0),
                int(stats["delivery_all_terminal"] or 0)
            )
        )
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise


@router.get('/{id}', response_model=schemas.Account)
async def read_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает аккаунт по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.Account`.

    Raises:
        HTTPException(404): Если аккаунт не найден.
    """
    operation = log_service.operation(
        action="account.read", user_id=_current_user.id, source="api",
    )
    details = {"target": {"requested_account_id": id}}
    try:
        operation.stage = "lookup"
        account = await crud.account.get(db=db, id=id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )
        return account
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise


@router.delete('/{id}', response_model=schemas.Account)
async def delete_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Удаляет аккаунт по идентификатору вместе со связанными файлами.

    Перед удалением аккаунта из базы данных проверяет наличие и удаляет:
    - Архив аккаунта (file_name) из папки app/upload/wa
    - Файл профиля (profile_file_name) из папки app/upload/wa/profile

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Удалённый объект `schemas.Account`.

    Raises:
        HTTPException(404): Если аккаунт не найден.
    """
    operation = log_service.operation(
        action="account.delete", user_id=_current_user.id, source="api",
    )
    details = {"target": {"requested_account_id": id}}
    try:
        operation.stage = "lookup"
        account = await crud.account.get(db=db, id=id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )

        details = {"target": _account_target(account, requested_id=id)}
        operation.stage = "prepare_response"
        response = schemas.Account.model_validate(account)
        # Files precede DELETE; independent writers wait for the boundary.
        file_deletion_result = await delete_account_files(
            response, operation=operation, details=details,
        )

        operation.stage = "log_files"
        if file_deletion_result["deleted_files"]:
            await asyncio.to_thread(
                logger.info,
                "Account files deleted successfully",
                event=E.SYSTEM.APP.SUCCESS,
                extra={
                    "account_id": id,
                    "deleted_files": file_deletion_result["deleted_files"]
                }
            )

        if file_deletion_result["errors"]:
            await asyncio.to_thread(
                logger.warning,
                "Some files could not be deleted",
                event=E.SYSTEM.APP.FAILURE,
                extra={
                    "account_id": id,
                    "errors": file_deletion_result["errors"]
                }
            )

        operation.stage = "db_delete"
        deleted_id = await crud.account.delete_returning_id(db, account_id=id)
        if deleted_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist',
            )
        operation.stage = "audit_success"
        await log_service.record(
            db, event="account.delete", source="api",
            user_id=operation.user_id,
            account_id=None, session_id=None, message_id=None,
            context=log_service.operation_context(operation, details=details),
            commit=False,
        )
        operation.stage = "commit"
        operation.db_outcome = "unknown"
        await db.commit()
        operation.db_outcome = "committed"
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise
    await log_service.flush_events(db, operation=operation)
    return response


@router.post('/delete', response_model=List[schemas.Account])
async def delete_accounts(
    *,
    db: AsyncSession = Depends(deps.get_db),
    data: schemas.AccountIds,
    _: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Удаляет аккаунты по списку идентификаторов вместе со связанными файлами.

    Для каждого аккаунта перед удалением из базы данных проверяет и удаляет:
    - Архив аккаунта (file_name) из папки app/upload/wa
    - Файл профиля (profile_file_name) из папки app/upload/wa/profile

    Если аккаунт не найден, он пропускается без ошибки. Ошибки удаления файлов
    логируются, но не останавливают процесс удаления других аккаунтов.
    Все удаления в БД выполняются в одной транзакции.

    Args:
        db: Асинхронная сессия базы данных.
        data: Список идентификаторов аккаунтов для удаления.
        _: Текущий активный пользователь.

    Returns:
        Список удалённых объектов `schemas.Account`.
    """
    operation = log_service.operation(
        action="account.delete_many", user_id=_.id, source="api",
    )
    request_details: dict[str, Any] = {"requested_account_ids": list(data.ids)}
    details = request_details
    try:
        accounts = []
        deletion_stats: dict[str, Any] = {
            "accounts_deleted": 0,
            "files_deleted": 0,
            "errors": []
        }

        seen: set[int] = set()
        for index, id in enumerate(data.ids):
            if id in seen:
                continue
            seen.add(id)
            details = {"target": {
                "requested_account_id": id, "request_index": index,
            }}
            operation.stage = "lookup"
            account = await crud.account.get(db=db, id=id)
            if not account:
                await asyncio.to_thread(
                    logger.warning, "Account not found, skipping",
                    event=E.SYSTEM.APP.FAILURE, extra={"account_id": id},
                )
                continue

            details = {"target": _account_target(
                account, requested_id=id, request_index=index,
            )}
            operation.stage = "prepare_response"
            response = schemas.Account.model_validate(account)
            file_deletion_result = await delete_account_files(
                response, operation=operation, details=details,
            )
            deletion_stats["files_deleted"] += len(
                file_deletion_result["deleted_files"],
            )
            deletion_stats["errors"].extend(file_deletion_result["errors"])

            operation.stage = "db_delete"
            deleted_id = await crud.account.delete_returning_id(
                db, account_id=id,
            )
            if deleted_id is None:
                continue
            operation.stage = "audit_success"
            await log_service.record(
                db, event="account.delete", source="api",
                user_id=operation.user_id,
                account_id=None, session_id=None, message_id=None,
                context=log_service.operation_context(
                    operation, details=details,
                ),
                commit=False,
            )
            accounts.append(response)
            deletion_stats["accounts_deleted"] += 1

        # Commit/log failures describe the whole request, not the last item.
        details = request_details
        operation.stage = "commit"
        operation.db_outcome = "unknown"
        await db.commit()
        operation.db_outcome = "committed"

        operation.stage = "success_log"
        await asyncio.to_thread(
            logger.info,
            "Batch account deletion completed",
            event=E.SYSTEM.APP.SUCCESS,
            extra={"stats": deletion_stats}
        )

    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise
    await log_service.flush_events(db, operation=operation)
    return accounts


@router.post('/upload')
async def upload_archive(
    file: UploadFile = File(...), db: AsyncSession = Depends(deps.get_db),
) -> JSONResponse:
    """Сохранить архив без обязательного JWT и записать файловый аудит."""
    operation = log_service.operation(
        action="account.file.upload", user_id=None, source="api",
    )
    operation.error_event = "account.file.upload.error"
    details = {
        "file_kind": "archive", "file_name": file.filename, "reason": "upload",
    }
    try:
        if not file.filename.endswith('.tar.gz'):
            raise HTTPException(
                status_code=400, detail='The file must have a .apk extension'
            )
        file_path = UPLOAD_DIR / file.filename

        operation.stage = "write_archive"
        await asyncio.to_thread(_write_archive, file, file_path)
        log_service.queue_event(
            operation, event="account.file.upload", details=details,
        )
        operation.error_event = None
        operation.stage = "prepare_response"
        response = JSONResponse(content={'file_name': str(file.filename)})
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise
    await log_service.flush_events(db, operation=operation)
    return response


@router.post('/remove')
async def remove_archive(
    request: Request, db: AsyncSession = Depends(deps.get_db),
) -> JSONResponse:
    """Удалить архив с независимым аудитом; отсутствующий файл даёт 404."""
    operation = log_service.operation(
        action="account.file.delete", user_id=None, source="api",
    )
    operation.error_event = "account.file.delete.error"
    details: dict[str, Any] = {
        "file_kind": "archive", "file_name": None, "reason": "remove",
    }
    try:
        form = await request.form()
        filename = form.get('file_name')
        details["file_name"] = log_service.safe_value(filename)
        if not filename or not filename.endswith(".tar.gz"):
            raise HTTPException(status_code=400, detail="Invalid file name")

        file_path = UPLOAD_DIR / filename

        operation.stage = "check_archive"
        if not await asyncio.to_thread(file_path.exists):
            raise HTTPException(status_code=404, detail="File not found")

        operation.stage = "delete_archive"
        try:
            await asyncio.to_thread(file_path.unlink)
        except FileNotFoundError as error:
            raise HTTPException(
                status_code=404, detail="File not found",
            ) from error
        log_service.queue_event(
            operation, event="account.file.delete", details=details,
        )
        operation.error_event = None
        operation.stage = "prepare_response"
        response = JSONResponse(
            content={"message": "File deleted successfully"},
        )
    except (Exception, asyncio.CancelledError) as error:
        await log_service.report_error(
            db, error, operation=operation, details=lambda: details,
        )
        raise
    await log_service.flush_events(db, operation=operation)
    return response


@router.post('/profile/upload')
async def upload_profile(profile_file: UploadFile = File(...)):
    try:
        if not profile_file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=400, detail='The file must have a .txt extension'
            )
        file_path = PROFILE_UPLOAD_DIR / profile_file.filename

        with file_path.open('wb') as buffer:
            shutil.copyfileobj(profile_file.file, buffer)

        return JSONResponse(content={'file_name': str(profile_file.filename)})
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post('/profile/remove')
async def remove_profile(request: Request):
    try:
        form = await request.form()
        filename = form.get('file_name')
        if not filename or not filename.endswith(".txt"):
            raise HTTPException(status_code=400, detail="Invalid file name")

        file_path = PROFILE_UPLOAD_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        file_path.unlink()

        return JSONResponse(content={"message": "File deleted successfully"})
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
