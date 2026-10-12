import asyncio
import errno
import json
import sys
from collections import deque
from collections.abc import Callable, Collection, Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from app.adapters.db.session import async_session
from app.core.logger import E, logger

import app.crud as crud
import app.models as models
import app.schemas as schemas


LogAction = Literal[
    "account.upload", "account.create", "account.update", "account.delete",
    "account.delete_many", "account.file.upload", "account.file.delete",
    "account.list", "account.read", "account.summary", "account.missing_files",
    "session.start", "session.finish", "session.ban",
]
LogSource = Literal["api", "ext_api"]
LogOutcome = Literal["not_committed", "unknown", "committed"]


@dataclass(frozen=True)
class _QueuedEvent:
    """Freeze wire data; retain original exceptions only for notes."""

    event: str | None
    source: LogSource
    user_id: int | None
    account_id: int | None
    operation_id: str
    action: LogAction
    stage: str
    db_outcome: LogOutcome
    context_json: str
    error_type: str | None
    http_status: int | None
    primary_error: BaseException | None = field(repr=False, compare=False)


@dataclass
class LogOperation:
    """Operation state; callers supply only trusted, scalar existing IDs."""

    action: LogAction
    user_id: int | None
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    stage: str = "validate"
    db_outcome: LogOutcome = "not_committed"
    error_code: str = "operation_failed"
    account_id: int | None = None
    session_id: int | None = None
    new_account_id: int | None = None
    new_session_id: int | None = None
    release_failed: bool = False
    transaction_cleanup_errors: dict[str, Any] = field(default_factory=dict)
    source: LogSource = "ext_api"
    error_event: str | None = None
    persist_error: bool = True
    _events: deque[_QueuedEvent] = field(default_factory=deque, repr=False)
    _pending_event: _QueuedEvent | None = field(default=None, repr=False)


class LogService:
    """Persist domain events and isolate best-effort operation error audits."""

    _UPLOAD_PARAMETER_FIELDS = (
        "number", "type", "limit", "cooldown", "geo",
        *(f"info_{i}" for i in range(1, 9)),
    )
    _UPLOAD_SNAPSHOT_FIELDS = (
        "id", "uuid", "user_id", "file_name", "profile_file_name", "status",
        "attempts", "session_count", "created_at", "updated_at",
        *_UPLOAD_PARAMETER_FIELDS,
    )
    _PRIVATE_DETAIL_FIELDS = frozenset({
        "hash", "headers", "header", "authorization", "api_key", "x_api_key",
        "password", "secret", "secret_key", "token", "access_token",
        "refresh_token", "cookie", "cookies", "content", "body", "data",
        "file_content", "file_contents", "message", "raw_message",
        "raw_messages", "exception_message", "detail", "sql", "statement",
        "params", "parameters_sql", "hash_value", "hashes", "raw_error",
        "raw_exception", "exception", "error", "errors", "traceback",
    })

    STATUS_MAP = {
        "account": {
            -1: "banned",
            0: "available",
            1: "active",
            2: "paused",
        },
        "session": {
            -1: "banned",
            0: "finished",
            1: "active",
            2: "paused",
        },
        "message": {
            -1: "waiting",
            0: "created",
            1: "sent",
            2: "delivered",
            3: "undelivered",
            4: "failed",
        },
    }

    def _normalize_status(
        self, event: str, status: str | int | None
    ) -> str | None:
        if status is None:
            return None

        if isinstance(status, str) and not status.lstrip("-").isdigit():
            return status.lower()

        try:
            raw_status = int(status)
        except (TypeError, ValueError):
            return str(status).lower()

        entity = event.split(".", 1)[0]
        return self.STATUS_MAP.get(entity, {}).get(
            raw_status, str(raw_status)
        )

    def _normalize_item(
        self, item: schemas.LogCreate | dict[str, Any]
    ) -> dict[str, Any]:
        data = item.model_dump(exclude_unset=True) \
            if isinstance(item, BaseModel) else dict(item)
        # Multi-row INSERT needs the account_id key in every item.
        data.setdefault("account_id", None)
        if "status" in data:
            data["status"] = self._normalize_status(
                data.get("event", ""), data["status"]
            )
        return data

    async def record(
        self,
        db: AsyncSession,
        *,
        event: str,
        source: str,
        account_id: int | None = None,
        session_id: int | None = None,
        message_id: int | None = None,
        user_id: int | None = None,
        status: str | int | None = None,
        context: dict[str, Any] | None = None,
        commit: bool = False
    ) -> models.Log:
        status = self._normalize_status(event, status)
        obj_in = schemas.LogCreate(
            event=event,
            source=source,
            account_id=account_id,
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            status=status,
            context=context or {}
        )
        return await crud.log.create(db=db, obj_in=obj_in, commit=commit)

    async def record_independent(
        self,
        *,
        event: str,
        source: str,
        account_id: int | None = None,
        session_id: int | None = None,
        message_id: int | None = None,
        user_id: int | None = None,
        status: str | int | None = None,
        context: dict[str, Any] | None = None,
    ) -> models.Log:
        """Commit an event in its own session; propagate persistence errors."""
        async with async_session() as db:
            record = await self.record(
                db,
                event=event,
                source=source,
                account_id=account_id,
                session_id=session_id,
                message_id=message_id,
                user_id=user_id,
                status=status,
                context=context,
                commit=False,
            )
            await db.commit()
            return record

    async def records(
        self,
        db: AsyncSession,
        *,
        items: Iterable[schemas.LogCreate | dict[str, Any]],
        commit: bool = False,
        returning: bool = False
    ) -> list[models.Log] | None:
        obj_list = [self._normalize_item(item) for item in items]
        if not obj_list:
            return [] if returning else None
        return await crud.log.insert(
            db=db, obj_list=obj_list, commit=commit, returning=returning
        )

    @staticmethod
    def operation(
        *,
        action: LogAction,
        user_id: int | None,
        source: LogSource = "ext_api",
    ) -> LogOperation:
        """Create isolated state with one UUID for all operation errors."""
        return LogOperation(action=action, user_id=user_id, source=source)

    @classmethod
    def operation_context(
        cls,
        operation: LogOperation,
        *,
        details: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Detach success metadata without claiming a future commit outcome.

        Callers supply metadata, not request bodies or exception messages.
        Sensitive field names and non-scalar objects are excluded recursively.
        """
        context: dict[str, Any] = {
            "operation_id": operation.operation_id,
            "action": operation.action,
            "user_id": operation.user_id,
        }
        if details is not None:
            try:
                context["details"] = cls._copy_details(details, redact=True)
            except (Exception, asyncio.CancelledError) as details_error:
                context["details_error"] = {
                    "type": cls._error_type(details_error),
                }
        return context

    @classmethod
    def queue_event(
        cls,
        operation: LogOperation,
        *,
        event: str | None,
        details: Mapping[str, Any] | None = None,
        error: BaseException | None = None,
        account_id: int | None = None,
    ) -> None:
        """Snapshot an observed fact synchronously, without releasing or I/O.

        Only the explicitly supplied, caller-trusted account FK is eligible;
        operation FKs are never inherited or promoted at flush time. A known
        new ID is excluded until its business commit has been acknowledged.
        event=None queues technical diagnostics only (e.g. a profile error).
        db_outcome describes the operation at observation time; a later commit
        does not rewrite the snapshot or promote an uncommitted foreign key.
        """
        context = cls.operation_context(operation, details=details)
        stage = cls._diagnostic_text(operation.stage)
        context.update(stage=stage, db_outcome=operation.db_outcome)
        error_type = None
        http_status = None
        if error is not None:
            error_type = cls._error_type(error)
            if isinstance(error, HTTPException):
                http_status = error.status_code
            context["error"] = {"type": error_type}
            try:
                context["error"] = cls.error_details(
                    error, operation.error_code,
                )
            except (Exception, asyncio.CancelledError) as context_error:
                context["context_error"] = {
                    "type": cls._error_type(context_error),
                }
        if (
            account_id == operation.new_account_id
            and operation.db_outcome != "committed"
        ):
            account_id = None
        operation._events.append(_QueuedEvent(
            event=event, source=operation.source, user_id=operation.user_id,
            account_id=account_id, operation_id=operation.operation_id,
            action=operation.action, stage=stage,
            db_outcome=operation.db_outcome,
            context_json=json.dumps(
                context, ensure_ascii=True, allow_nan=False,
            ),
            error_type=error_type, http_status=http_status,
            primary_error=error,
        ))

    @staticmethod
    def _safe_text(value: str) -> str:
        return value.encode("utf-8", "backslashreplace").decode().replace(
            "\x00", r"\u0000",
        )

    @classmethod
    def safe_value(cls, value: Any) -> str | int | bool | None:
        """Copy known scalars without stringifying arbitrary objects."""
        if isinstance(value, Enum):
            value = value.value
        if isinstance(value, str):
            return cls._safe_text(value)
        if value is None or isinstance(value, (int, bool)):
            return value
        if isinstance(value, (datetime, date)):
            return cls._safe_text(value.isoformat())
        if isinstance(value, (UUID, Path)):
            return cls._safe_text(str(value))
        return "[omitted]"

    @classmethod
    def upload_snapshot(
        cls, values: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Copy approved account fields without ORM/request objects."""
        if values is None:
            return None
        return {
            name: cls.safe_value(values[name])
            for name in cls._UPLOAD_SNAPSHOT_FIELDS if name in values
        }

    @classmethod
    def _upload_file_metadata(cls, file: Any) -> dict[str, Any] | None:
        if file is None:
            return None
        return {
            "filename": cls.safe_value(file.filename),
            "content_type": cls.safe_value(file.content_type),
            "size": cls.safe_value(file.size),
        }

    @classmethod
    def upload_details(
        cls,
        *,
        request: Any,
        obj_in: schemas.AccountUpload,
        provided_fields: Collection[str],
        file: Any,
        profile_file: Any = None,
        branch: Literal["create", "update"] | None,
        before: Mapping[str, Any] | None = None,
        requested: Mapping[str, Any] | None = None,
        returned: Mapping[str, Any] | None = None,
        files_written: Collection[str],
        archive_directory: Path,
        profile_directory: Path,
        cleanup: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build only account-specific details, excluding headers and hash."""
        known_fields = set(cls._UPLOAD_PARAMETER_FIELDS) | {
            "hash", "file", "profile_file",
        }
        details = {
            "branch": cls.safe_value(branch),
            "files_written": [
                cls.safe_value(value) for value in files_written
            ],
            "request": {
                "method": cls.safe_value(request.method),
                "path": cls.safe_value(request.scope["path"]),
                "parameters": cls.upload_snapshot(obj_in.model_dump(
                    include=set(cls._UPLOAD_PARAMETER_FIELDS),
                )),
                "provided_fields": sorted(set(provided_fields) & known_fields),
                "hash_nonempty": bool(obj_in.hash),
                "files": {
                    "archive": cls._upload_file_metadata(file),
                    "profile": cls._upload_file_metadata(profile_file),
                },
            },
            "storage": {
                "archive_directory": cls.safe_value(archive_directory),
                "profile_directory": cls.safe_value(profile_directory),
            },
            "before": cls.upload_snapshot(before),
            "requested": cls.upload_snapshot(requested),
            "returned": cls.upload_snapshot(returned),
        }
        if cleanup is not None:
            details["cleanup"] = {
                cls._safe_text(key): cls.safe_value(value)
                for key, value in cleanup.items() if isinstance(key, str)
            }
        return details

    @classmethod
    def _diagnostic_text(cls, value: str) -> str:
        return cls._safe_text(value[:160])[:160]

    @classmethod
    def _error_type(cls, error: BaseException) -> str:
        return cls._diagnostic_text(type(error).__name__)

    @classmethod
    def error_details(
        cls, error: BaseException, code: str = "operation_failed",
    ) -> dict[str, Any]:
        """Bound diagnostics, omitting messages, SQL, locals and OS paths."""
        details: dict[str, Any] = {
            "type": cls._error_type(error),
            "code": "cancelled" if isinstance(error, asyncio.CancelledError)
            else cls._diagnostic_text(code),
            "message": "Operation failed",
        }
        if isinstance(error, SQLAlchemyError):
            details["message"] = "Database operation failed"
        elif isinstance(error, HTTPException):
            details["message"] = "HTTP request processing failed"
            if isinstance(error.status_code, int):
                details["http_status"] = error.status_code
        elif isinstance(error, OSError):
            details["message"] = "Operating system operation failed"

        frames = []
        traceback = error.__traceback__
        while traceback is not None:
            frame = traceback.tb_frame.f_code
            frames.append({
                "file": cls._diagnostic_text(
                    frame.co_filename.replace("\\", "/").rsplit("/", 1)[-1],
                ),
                "function": cls._diagnostic_text(frame.co_name),
                "line": traceback.tb_lineno,
            })
            frames = frames[-12:]
            traceback = traceback.tb_next
        details["traceback"] = frames

        pending = [error]
        visited: set[int] = set()
        cause_types = []
        while pending and len(visited) < 12:
            current = pending.pop()
            if id(current) in visited:
                continue
            visited.add(id(current))
            if current is not error:
                cause_types.append(cls._error_type(current))
            sqlstate = (
                getattr(current, "sqlstate", None)
                or getattr(current, "pgcode", None)
            )
            if (
                isinstance(sqlstate, str) and len(sqlstate) == 5
                and sqlstate.isascii() and sqlstate.isalnum()
            ):
                details.setdefault("sqlstate", sqlstate)
            for name in (
                "schema_name", "table_name", "column_name", "constraint_name",
            ):
                value = getattr(current, name, None)
                if isinstance(value, str):
                    details.setdefault(name, cls._diagnostic_text(value))
            if isinstance(current, OSError) and isinstance(current.errno, int):
                details.setdefault("errno", current.errno)
                details.setdefault("errno_name", errno.errorcode.get(
                    current.errno,
                ))
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

    @classmethod
    def _copy_details(
        cls, value: Any, depth: int = 0, *, redact: bool = False,
    ) -> Any:
        """Detach callback metadata and make nested containers JSONB-safe."""
        if depth >= 12:
            return "[omitted]"
        if isinstance(value, Mapping):
            return {
                cls._safe_text(key): cls._copy_details(
                    item, depth + 1, redact=redact,
                )
                for key, item in value.items() if isinstance(key, str)
                and (not redact or (
                    key.lower().replace("-", "_")
                    not in cls._PRIVATE_DETAIL_FIELDS
                    and not key.lower().replace("-", "_").endswith("_hash")
                ))
            }
        if isinstance(value, (list, tuple)):
            return [cls._copy_details(item, depth + 1, redact=redact)
                    for item in value]
        return cls.safe_value(value)

    async def _release(
        self, db: AsyncSession, operation: LogOperation,
    ) -> bool:
        if operation.release_failed:
            return False
        for method in ("rollback", "close"):
            try:
                await getattr(db, method)()
                if not db.in_transaction():
                    return True
                operation.transaction_cleanup_errors[method] = {
                    "type": "TransactionStillActive",
                }
            except (Exception, asyncio.CancelledError) as error:
                operation.transaction_cleanup_errors[method] = {
                    "type": self._error_type(error),
                }
        operation.release_failed = True
        return False

    @staticmethod
    def _add_note(error: BaseException, note: str) -> bool:
        try:
            BaseException.add_note(error, note)
        except (Exception, asyncio.CancelledError):
            # Even an invalid __notes__ attribute cannot replace the primary.
            return False
        return True

    async def _emit(
        self,
        context: dict[str, Any],
        primary_error: BaseException,
        operation: LogOperation | _QueuedEvent,
    ) -> None:
        logger_error_type: str | None = None
        try:
            event = E.SYSTEM.API.ERROR
            http_status = None
            if isinstance(operation, _QueuedEvent):
                http_status = operation.http_status
            elif isinstance(primary_error, HTTPException):
                http_status = primary_error.status_code
            if http_status is not None:
                if http_status == 404:
                    event = E.SYSTEM.API.NOT_FOUND
                elif 400 <= http_status < 500:
                    event = E.SYSTEM.API.FAILURE
            await asyncio.to_thread(
                logger.error, "Operation failed", event=event, extra=context,
            )
        except (Exception, asyncio.CancelledError) as logger_error:
            logger_error_type = self._error_type(logger_error)
        # Logging handlers may swallow I/O failures. Unconfirmed DB audits
        # must reach stderr even when the logger returns successfully.
        confirmed = context.get("audit_confirmed", False)
        if (
            (confirmed or context.get("audit_skipped", False))
            and logger_error_type is None
        ):
            return
        await self._emit_emergency(
            primary_error, operation, audit_confirmed=confirmed,
            logger_error_type=logger_error_type,
        )

    async def _emit_emergency(
        self,
        primary_error: BaseException,
        operation: LogOperation | _QueuedEvent,
        *,
        audit_confirmed: bool = False,
        logger_error_type: str | None = None,
        finalizer_error_type: str | None = None,
    ) -> None:
        """Emit minimal diagnostics without context builders or the logger."""
        try:
            if isinstance(operation, _QueuedEvent):
                audit_event = operation.event
            else:
                audit_event = (
                    operation.error_event
                    or f"{operation.action.split('.', 1)[0]}.error"
                ) if operation.persist_error else None
            emergency = {
                "event": f"{audit_event}.audit_unavailable" if audit_event
                else f"{operation.action}.diagnostics_unavailable",
                "operation_id": operation.operation_id,
                "action": operation.action,
                "stage": self._diagnostic_text(operation.stage),
                "db_outcome": operation.db_outcome,
                "audit_confirmed": audit_confirmed,
                "error_type": self._error_type(primary_error),
                "logger_error_type": logger_error_type,
            }
            if audit_event is None:
                emergency["audit_skipped"] = True
            if isinstance(operation, _QueuedEvent):
                emergency.update(
                    source=operation.source, user_id=operation.user_id,
                    account_id=operation.account_id,
                    target=json.loads(operation.context_json).get(
                        "details", {},
                    ).get("target"),
                )
                if operation.error_type is not None:
                    emergency["error_type"] = operation.error_type
            if finalizer_error_type is not None:
                emergency["finalizer_error_type"] = finalizer_error_type
            await asyncio.to_thread(
                sys.stderr.write, json.dumps(emergency) + "\n",
            )
        except (Exception, asyncio.CancelledError) as output_error:
            self._add_note(
                primary_error,
                "Operation audit diagnostics unavailable "
                f"(operation_id={operation.operation_id}, "
                f"output_error={self._error_type(output_error)}).",
            )

    async def _write_event(
        self, operation: LogOperation, fact: _QueuedEvent, released: bool,
    ) -> None:
        context = json.loads(fact.context_json)
        context.update(
            transaction_released=released,
            transaction_cleanup_errors=self._copy_details(
                operation.transaction_cleanup_errors,
            ),
        )
        primary = fact.primary_error
        confirmed = False
        if fact.event is None:
            context["audit_skipped"] = True
        elif released and not operation.release_failed:
            try:
                # Isolate a writer that self-cancels, even without a final
                # await. Its unknown commit is consumed once, never retried.
                await asyncio.create_task(self.record_independent(
                    event=fact.event, source=fact.source, user_id=fact.user_id,
                    account_id=fact.account_id, context=context,
                ))
                confirmed = True
            except (Exception, asyncio.CancelledError) as journal_error:
                context["error_journal_error"] = {
                    "type": self._error_type(journal_error),
                }
                if primary is None:
                    primary = journal_error
        if primary is None and (confirmed or fact.event is None):
            return
        await self._emit(
            {**context, "audit_confirmed": confirmed},
            primary if primary is not None else RuntimeError(), fact,
        )

    async def _event_emergency(
        self, fact: _QueuedEvent, failure_type: str,
    ) -> None:
        primary = fact.primary_error
        if primary is None:
            primary = RuntimeError()
        self._add_note(
            primary, "Operation event finalizer failed "
            f"(operation_id={fact.operation_id}, error_type={failure_type}).",
        )
        try:
            await asyncio.create_task(self._emit_emergency(
                primary, fact, finalizer_error_type=failure_type,
            ))
        except (Exception, asyncio.CancelledError) as output_error:
            self._add_note(
                primary, "Operation audit diagnostics unavailable "
                f"(operation_id={fact.operation_id}, "
                f"output_error={self._error_type(output_error)}).",
            )

    async def _drain_events(
        self, operation: LogOperation, released: bool,
    ) -> None:
        while operation._events:
            fact = operation._events.popleft()
            operation._pending_event = fact
            try:
                await asyncio.create_task(self._write_event(
                    operation, fact, released and not operation.release_failed,
                ))
            except (Exception, asyncio.CancelledError) as finalizer_error:
                operation.release_failed = True
                await self._event_emergency(
                    fact, self._error_type(finalizer_error),
                )
            finally:
                operation._pending_event = None

    async def _emergency_all(
        self, error: BaseException | None, operation: LogOperation,
        failure_type: str,
    ) -> None:
        """Consume all unconfirmed snapshots without retrying any DB writer."""
        while operation._pending_event is not None or operation._events:
            fact = operation._pending_event
            operation._pending_event = None
            if fact is None:
                fact = operation._events.popleft()
            await self._event_emergency(fact, failure_type)
        if error is not None:
            await self._emit_emergency(
                error, operation, finalizer_error_type=failure_type,
            )

    async def _finalize(
        self,
        db: AsyncSession,
        primary_error: BaseException | None,
        *,
        operation: LogOperation,
        details: Callable[[], dict[str, Any]] | None,
    ) -> bool:
        released = await self._release(db, operation)
        await self._drain_events(operation, released)
        released = released and not operation.release_failed
        if primary_error is None:
            return released
        context: dict[str, Any] = {
            "operation_id": operation.operation_id,
            "action": operation.action,
            "user_id": operation.user_id,
            "stage": self._diagnostic_text(operation.stage),
            "db_outcome": operation.db_outcome,
            "error": {"type": self._error_type(primary_error)},
            "transaction_cleanup_errors": self._copy_details(
                operation.transaction_cleanup_errors,
            ),
            "transaction_released": released,
        }
        try:
            context["error"] = self.error_details(
                primary_error, operation.error_code,
            )
        except (Exception, asyncio.CancelledError) as context_error:
            context["context_error"] = {
                "type": self._error_type(context_error),
            }
        if details is not None:
            try:
                extra = details()
                if not isinstance(extra, dict):
                    raise TypeError("Operation details must be a dictionary")
                context["details"] = self._copy_details(extra)
            except (Exception, asyncio.CancelledError) as details_error:
                context["details_error"] = {
                    "type": self._error_type(details_error),
                }

        confirmed = False
        if not operation.persist_error:
            context["audit_skipped"] = True
        elif released:
            # A failed commit stays unknown even after successful rollback.
            committed = operation.db_outcome == "committed"
            account_id = operation.account_id
            session_id = operation.session_id
            if account_id is None and committed:
                account_id = operation.new_account_id
            if session_id is None and committed:
                session_id = operation.new_session_id
            try:
                await self.record_independent(
                    event=operation.error_event
                    or f"{operation.action.split('.', 1)[0]}.error",
                    source=operation.source, user_id=operation.user_id,
                    account_id=account_id, session_id=session_id,
                    context=context,
                )
                confirmed = True
            except (Exception, asyncio.CancelledError) as journal_error:
                context["error_journal_error"] = {
                    "type": self._error_type(journal_error),
                }
        await self._emit(
            {**context, "audit_confirmed": confirmed},
            primary_error, operation,
        )
        return released

    async def _finalize_protected(
        self,
        db: AsyncSession,
        primary_error: BaseException | None,
        *,
        operation: LogOperation,
        details: Callable[[], dict[str, Any]] | None,
    ) -> bool:
        """Keep unexpected-finalizer diagnostics inside the shielded task."""
        try:
            # A separate child also contains self-cancellation without a final
            # await: the fallback task must not inherit its pending cancel.
            return await asyncio.create_task(self._finalize(
                db, primary_error, operation=operation, details=details,
            ))
        except (Exception, asyncio.CancelledError) as finalizer_error:
            operation.release_failed = True
            finalizer_error_type = self._error_type(finalizer_error)
            if primary_error is not None:
                self._add_note(
                    primary_error, "Operation error finalizer failed "
                    f"(operation_id={operation.operation_id}, "
                    f"error_type={finalizer_error_type}).",
                )
            # Release/audit outcome is unconfirmed. Do not retry a DB writer
            # or rely on notes: post-commit callers may discard the error.
            await self._emergency_all(
                primary_error, operation, finalizer_error_type,
            )
            return False

    async def report_error(
        self,
        db: AsyncSession,
        error: BaseException,
        *,
        operation: LogOperation,
        details: Callable[[], dict[str, Any]] | None = None,
    ) -> bool:
        """Drain prior facts, report an error and return transaction release.

        persist_error=False retains cleanup/diagnostics without a DB event;
        error_event=None preserves the legacy <entity>.error selection.
        """
        return await self._finish(
            db, error, operation=operation, details=details,
        )

    async def flush_events(
        self, db: AsyncSession, *, operation: LogOperation,
    ) -> bool:
        """Release and drain the whole buffer before propagating cancellation.

        The bool confirms release, not audit success. Facts are consumed once;
        writer failures never create file-error records or stop business work.
        """
        return await self._finish(db, None, operation=operation, details=None)

    async def _finish(
        self,
        db: AsyncSession,
        error: BaseException | None,
        *,
        operation: LogOperation,
        details: Callable[[], dict[str, Any]] | None,
    ) -> bool:
        """Confirm transaction release and preserve cancellation.

        The result describes release, not audit success.
        Finalization finishes before dependency teardown, including repeated
        cancellation. An unconfirmed release latches on the operation and
        blocks all subsequent independent writers for that operation. If the
        finalizer fails unexpectedly, emergency output completes first. A
        terminated protected task gets one emergency attempt; failure of that
        attempt is noted without retrying a completed/cancelled task.
        """
        parent = asyncio.current_task()
        initial_cancelling = parent.cancelling() if parent is not None else 0
        finalizer: asyncio.Task[bool] | asyncio.Task[None]
        finalizer = asyncio.create_task(self._finalize_protected(
            db, error, operation=operation, details=details,
        ))
        cancellation: asyncio.CancelledError | None = None
        emergency_started = False
        released = False
        while True:
            try:
                result = await asyncio.shield(finalizer)
                released = not emergency_started and result is True
                break
            except asyncio.CancelledError as cancelled:
                if not finalizer.cancelled():
                    cancellation = cancellation or cancelled
                    continue
                # A child's cancellation is not a new caller cancellation.
                # The initial count may belong to the primary error itself.
                if (
                    parent is not None
                    and parent.cancelling() > initial_cancelling
                ):
                    cancellation = cancellation or cancelled
                failure_type = self._error_type(cancelled)
            except Exception as finalizer_error:
                failure_type = self._error_type(finalizer_error)

            operation.release_failed = True
            phase = "emergency" if emergency_started else "protected"
            if error is not None:
                self._add_note(
                    error, f"Operation audit {phase} finalizer failed "
                    f"(operation_id={operation.operation_id}, "
                    f"error_type={failure_type}).",
                )
            if emergency_started:
                break
            emergency_started = True
            finalizer = asyncio.create_task(self._emergency_all(
                error, operation, failure_type,
            ))
        if cancellation is not None:
            raise cancellation
        return released


log_service = LogService()
