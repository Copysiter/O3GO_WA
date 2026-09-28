import asyncio
import errno
import json
import sys
import uuid
import time
import aiofiles

from collections.abc import Collection, Mapping
from enum import Enum
from traceback import walk_tb
from typing import Any, Literal
from pathlib import Path
from urllib.parse import urljoin
from datetime import date, datetime

from fastapi import (
    Request, APIRouter, Depends, UploadFile, File, HTTPException, status
)
from fastapi.responses import FileResponse
from sqlalchemy import select, update, func, or_
from sqlalchemy.exc import SQLAlchemyError
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

_UPLOAD_PARAMETER_FIELDS = (
    "number", "type", "limit", "cooldown", "geo",
    *(f"info_{i}" for i in range(1, 9)),
)
_UPLOAD_SNAPSHOT_FIELDS = (
    "id", "uuid", "user_id", "file_name", "profile_file_name", "status",
    "attempts", "session_count", "created_at", "updated_at",
    *_UPLOAD_PARAMETER_FIELDS,
)


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


def _safe_upload_text(value: str) -> str:
    """Represent NUL and lone surrogates as printable escapes for JSONB."""
    text = value.encode("utf-8", errors="backslashreplace").decode("utf-8")
    return text.replace("\x00", r"\u0000")


def _safe_upload_value(value: Any) -> str | int | bool | None:
    """Encode known scalar metadata without stringifying arbitrary objects."""
    if isinstance(value, Enum):
        value = value.value
    if isinstance(value, str):
        return _safe_upload_text(value)
    if value is None or isinstance(value, (int, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return _safe_upload_text(value.isoformat())
    if isinstance(value, (uuid.UUID, Path)):
        return _safe_upload_text(str(value))
    return "[omitted]"


def _upload_snapshot(
    values: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Copy only approved account fields into JSON-compatible metadata."""
    if values is None:
        return None
    return {
        field: _safe_upload_value(values[field])
        for field in _UPLOAD_SNAPSHOT_FIELDS if field in values
    }


def _upload_file_metadata(file: UploadFile | None) -> dict[str, Any] | None:
    """Describe an upload without reading its body or copying its headers."""
    if file is None:
        return None
    return {
        "filename": _safe_upload_value(file.filename),
        "content_type": _safe_upload_value(file.content_type),
        "size": _safe_upload_value(file.size),
    }


def _upload_error_details(error: BaseException) -> dict[str, Any]:
    """Keep diagnostic codes and stack locations, not SQL or raw messages."""
    details: dict[str, Any] = {
        "type": _safe_upload_text(type(error).__name__),
        "message": "Upload operation failed",
        "traceback": [
            {
                "file": _safe_upload_text(frame.f_code.co_filename),
                "function": _safe_upload_text(frame.f_code.co_name),
                "line": line,
            }
            for frame, line in walk_tb(error.__traceback__)
        ],
    }
    if isinstance(error, SQLAlchemyError):
        details["message"] = "Database operation failed"
    elif isinstance(error, HTTPException):
        details["message"] = "HTTP request processing failed"
        if isinstance(error.status_code, int):
            details["http_status"] = error.status_code
    elif isinstance(error, OSError):
        details["message"] = "Operating system operation failed"

    pending = [error]
    visited: set[int] = set()
    cause_types = []
    while pending:
        current = pending.pop()
        if id(current) in visited:
            continue
        visited.add(id(current))
        if current is not error:
            cause_types.append(_safe_upload_text(type(current).__name__))
        sqlstate = (
            getattr(current, "sqlstate", None)
            or getattr(current, "pgcode", None)
        )
        if (
            isinstance(sqlstate, str) and len(sqlstate) == 5
            and sqlstate.isascii() and sqlstate.isalnum()
        ):
            details.setdefault("sqlstate", sqlstate)
        for field in (
            "schema_name", "table_name", "column_name", "constraint_name",
        ):
            value = getattr(current, field, None)
            if isinstance(value, str):
                details.setdefault(field, _safe_upload_text(value))
        if isinstance(current, OSError):
            if isinstance(current.errno, int):
                details.setdefault("errno", current.errno)
                details.setdefault("errno_name", errno.errorcode.get(
                    current.errno
                ))
            if current.filename is not None:
                details.setdefault(
                    "filename", _safe_upload_value(current.filename)
                )
        original = getattr(current, "orig", None)
        if isinstance(original, BaseException):
            pending.append(original)
        cause = current.__cause__
        if cause is None and not current.__suppress_context__:
            cause = current.__context__
        if isinstance(cause, BaseException):
            pending.append(cause)
    details["cause_types"] = cause_types
    return details


def _build_upload_error_context(
    *,
    request: Request,
    obj_in: schemas.AccountUpload,
    provided_fields: Collection[str],
    file: UploadFile,
    operation_id: uuid.UUID,
    user_id: int,
    branch: Literal["create", "update"] | None,
    stage: str,
    db_outcome: Literal["not_committed", "committed", "unknown"],
    error: BaseException,
    profile_file: UploadFile | None = None,
    before: Mapping[str, Any] | None = None,
    requested: Mapping[str, Any] | None = None,
    returned: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Snapshot safe diagnostics without retaining request or ORM objects."""
    known_fields = set(_UPLOAD_PARAMETER_FIELDS) | {
        "hash", "file", "profile_file",
    }
    return {
        "operation_id": _safe_upload_value(operation_id),
        "user_id": _safe_upload_value(user_id),
        "branch": _safe_upload_value(branch),
        "stage": _safe_upload_value(stage),
        "db_outcome": _safe_upload_value(db_outcome),
        "request": {
            "method": _safe_upload_text(request.method),
            "path": _safe_upload_text(request.scope["path"]),
            "parameters": _upload_snapshot(obj_in.model_dump(
                include=set(_UPLOAD_PARAMETER_FIELDS)
            )),
            "provided_fields": sorted(set(provided_fields) & known_fields),
            "hash_nonempty": bool(obj_in.hash),
            "files": {
                "archive": _upload_file_metadata(file),
                "profile": _upload_file_metadata(profile_file),
            },
        },
        "storage": {
            "archive_directory": _safe_upload_value(UPLOAD_DIR),
            "profile_directory": _safe_upload_value(PROFILE_UPLOAD_DIR),
        },
        "before": _upload_snapshot(before),
        "requested": _upload_snapshot(requested),
        "returned": _upload_snapshot(returned),
        "error": _upload_error_details(error),
    }


async def _save_upload_file(file: UploadFile, file_path: Path) -> None:
    """Write and close a new upload without removing existing artifacts."""
    content = await file.read()
    async with aiofiles.open(file_path, "wb") as destination:
        await destination.write(content)


async def _rollback_upload_transaction(
    session: AsyncSession,
) -> dict[str, Any]:
    """Release the transaction before audit, retaining safe error details."""
    errors: dict[str, Any] = {}
    if not session.in_transaction():
        return errors
    try:
        await session.rollback()
    except (Exception, asyncio.CancelledError) as rollback_error:
        errors["rollback"] = _upload_error_details(rollback_error)
        try:
            await session.close()
        except (Exception, asyncio.CancelledError) as close_error:
            errors["close"] = _upload_error_details(close_error)
    return errors


async def _emit_upload_audit_failure(
    *,
    operation_id: uuid.UUID,
    stage: str,
    db_outcome: str,
    error: BaseException,
    logger_error: BaseException,
) -> None:
    """Emit a bounded emergency event without request data or raw errors."""
    event = {
        "event": "account.error.audit_unavailable",
        "operation_id": str(operation_id),
        "stage": _safe_upload_text(stage),
        "db_outcome": _safe_upload_text(db_outcome),
        "error_type": _safe_upload_text(type(error).__name__),
        "logger_error_type": _safe_upload_text(type(logger_error).__name__),
    }
    try:
        await asyncio.to_thread(sys.stderr.write, json.dumps(event) + "\n")
    except (Exception, asyncio.CancelledError) as output_error:
        error.add_note(
            "Account upload audit and emergency output unavailable "
            f"(operation_id={operation_id}, "
            f"output_error={_safe_upload_text(type(output_error).__name__)})."
        )


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
    operation_id = uuid.uuid4()
    before: dict[str, Any] | None = None
    requested: dict[str, Any] | None = None
    returned: dict[str, Any] | None = None
    branch: Literal["create", "update"] | None = None
    stage = "validate"
    db_outcome: Literal["not_committed", "committed", "unknown"] = (
        "not_committed"
    )
    provided_fields: set[str] = set()
    files_written: list[str] = []
    session_release_failed = False
    transaction_cleanup_errors: dict[str, Any] = {}

    async def finalize_error(
        error: BaseException, *, cleanup: dict[str, Any] | None = None,
    ) -> bool:
        """Audit after releasing the business session, preserving the error."""
        nonlocal session_release_failed
        context: dict[str, Any] = {
            "operation_id": str(operation_id),
            "user_id": actor_id,
            "branch": branch,
            "stage": stage,
            "db_outcome": db_outcome,
            "files_written": list(files_written),
            "error": {
                "type": _safe_upload_text(type(error).__name__),
                "message": "Upload operation failed",
            },
        }
        cleanup_errors = await _rollback_upload_transaction(session)
        transaction_cleanup_errors.update(cleanup_errors)
        if "close" in cleanup_errors:
            session_release_failed = True
        context["transaction_cleanup_errors"] = dict(
            transaction_cleanup_errors
        )
        transaction_released = (
            not session_release_failed and not session.in_transaction()
        )
        try:
            context.update(_build_upload_error_context(
                request=request,
                obj_in=obj_in,
                provided_fields=provided_fields,
                file=file,
                profile_file=profile_file,
                operation_id=operation_id,
                user_id=actor_id,
                branch=branch,
                stage=stage,
                db_outcome=db_outcome,
                before=before,
                requested=requested,
                returned=returned,
                error=error,
            ))
            if cleanup is not None:
                context["cleanup"] = {
                    key: _safe_upload_value(value)
                    for key, value in cleanup.items()
                }
            if transaction_released:
                account_id = before["id"] if before is not None else None
                if account_id is None and db_outcome == "committed":
                    account_id = returned["id"] if returned else None
                await log_service.record_independent(
                    event="account.error",
                    source="ext_api",
                    account_id=account_id,
                    user_id=actor_id,
                    context=context,
                )
                return True
        except (Exception, asyncio.CancelledError) as journal_error:
            context["error_journal_error"] = _upload_error_details(
                journal_error
            )

        # A failed close leaves the transaction outcome uncertain: opening an
        # independent audit transaction could wait on its account foreign key.
        try:
            await asyncio.to_thread(
                logger.error,
                "Account upload error journal unavailable",
                event=E.SYSTEM.API.ERROR,
                extra=context,
            )
        except (Exception, asyncio.CancelledError) as logger_error:
            await _emit_upload_audit_failure(
                operation_id=operation_id, stage=stage,
                db_outcome=db_outcome, error=error, logger_error=logger_error,
            )
        return transaction_released

    async def report_error(
        error: BaseException, *, cleanup: dict[str, Any] | None = None,
    ) -> bool:
        finalizer = asyncio.create_task(finalize_error(error, cleanup=cleanup))
        cancellation: asyncio.CancelledError | None = None
        while True:
            try:
                # Dependency teardown must not race with this session's audit.
                released = await asyncio.shield(finalizer)
                break
            except asyncio.CancelledError as cancelled:
                if finalizer.cancelled():
                    raise
                if cancellation is None:
                    cancellation = cancelled
        if cancellation is not None:
            raise cancellation
        return released

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

        stage = "lookup"
        await session.begin()
        before = await crud.account.get_upload_snapshot(
            db=session, number=obj_in.number, user_id=actor_id
        )
        await session.commit()
        branch = "update" if before is not None else "create"

        stage = "validate"
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

        stage = "write_archive"
        await _save_upload_file(file, UPLOAD_DIR / file_name)
        files_written.append("archive")
        if profile_file is not None and profile_file_name is not None:
            stage = "write_profile"
            await _save_upload_file(
                profile_file, PROFILE_UPLOAD_DIR / profile_file_name
            )
            files_written.append("profile")

        stage = "db_write"
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

        stage = "verify_returning"
        account_values = vars(account) if account is not None else None
        returned = _upload_snapshot(account_values)
        if (
            account_values is None or account_values.get("id") is None
            or (before is not None and account_values["id"] != before["id"])
            or account_values.get("file_name") != file_name
            or "profile_file_name" not in account_values
            or account_values.get("profile_file_name") != profile_file_name
            or account_values.get("user_id") != actor_id
        ):
            raise RuntimeError("Account upload RETURNING verification failed")

        stage = "audit"
        await log_service.record(
            session,
            event=f"account.{branch}",
            source="ext_api",
            account_id=account_values["id"],
            user_id=actor_id,
            status=account_values.get("status"),
            commit=False,
        )
        stage = "prepare_response"
        response = schemas.AccountExternal.model_validate({
            **account_values, "user": response_user,
        })
        stage = "commit"
        db_outcome = "unknown"
        await session.commit()
        db_outcome = "committed"
    except (Exception, asyncio.CancelledError) as error:
        await report_error(error)
        raise

    stage = "cleanup"
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
            released = await report_error(error, cleanup=cleanup)
            if isinstance(error, asyncio.CancelledError):
                raise
            if not released:
                break

    if not session_release_failed and not session.in_transaction():
        stage = "success_log"
        try:
            await asyncio.to_thread(
                logger.info,
                "Account updated successfully" if before is not None
                else "Account archive uploaded successfully",
                event=E.SYSTEM.API.RESPONSE,
                extra={
                    "user_id": actor_id,
                    "account_id": response.id,
                    "account_uuid": _safe_upload_value(response.uuid),
                    "old_uuid": _safe_upload_value(
                        before.get("uuid") if before is not None else None
                    ),
                    "file_name": _safe_upload_value(response.file_name),
                    "profile_file_name": _safe_upload_value(
                        response.profile_file_name
                    ),
                },
            )
        except (Exception, asyncio.CancelledError) as error:
            await report_error(error)
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
