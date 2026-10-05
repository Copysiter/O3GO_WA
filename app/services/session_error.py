"""Best-effort session-operation audit using the existing log structure."""

import asyncio
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException

from app.core.logger import E, logger
from app.services.log import log_service


def _safe_text(value: str) -> str:
    return value.encode("utf-8", "backslashreplace").decode().replace(
        "\x00", "\\0",
    )[:160]


def _error_type(error: BaseException) -> str:
    return _safe_text(type(error).__name__)


def _error_details(error: BaseException, code: str) -> dict[str, Any]:
    """Exclude raw messages, SQL, request data and locals from diagnostics."""
    details: dict[str, Any] = {
        "type": _error_type(error),
        "code": "cancelled" if isinstance(error, asyncio.CancelledError)
        else code,
        "message": "Session operation failed",
    }
    if isinstance(error, HTTPException):
        details["http_status"] = error.status_code
    frames = []
    traceback = error.__traceback__
    while traceback is not None:
        frame = traceback.tb_frame.f_code
        frames.append({
            "file": _safe_text(frame.co_filename.rsplit("/", 1)[-1]),
            "function": _safe_text(frame.co_name),
            "line": traceback.tb_lineno,
        })
        traceback = traceback.tb_next
    details["traceback"] = frames[-12:]
    return details


@dataclass
class SessionErrorAudit:
    """Capture scalar IDs before rollback can expire ORM objects."""

    action: Literal["session.start", "session.finish", "session.ban"]
    user_id: int
    operation_id: str = field(default_factory=lambda: str(uuid4()))
    stage: str = "validate"
    db_outcome: Literal["not_committed", "unknown", "committed"] = (
        "not_committed"
    )
    error_code: str = "operation_failed"
    account_id: int | None = None
    session_id: int | None = None
    new_account_id: int | None = None
    new_session_id: int | None = None

    async def _release(
        self, db: AsyncSession, context: dict[str, Any],
    ) -> bool:
        errors: dict[str, Any] = {}
        context["transaction_cleanup_errors"] = errors
        for method in ("rollback", "close"):
            try:
                await getattr(db, method)()
                if not db.in_transaction():
                    return True
                errors[method] = {"type": "TransactionStillActive"}
            except (Exception, asyncio.CancelledError) as error:
                errors[method] = {"type": _error_type(error)}
        return False

    async def _emit(
        self, context: dict[str, Any], primary_error: BaseException,
    ) -> None:
        logger_error_type: str | None = None
        try:
            await asyncio.to_thread(
                logger.error, "Session operation failed",
                event=E.SYSTEM.API.ERROR, extra=context,
            )
        except (Exception, asyncio.CancelledError) as logger_error:
            logger_error_type = _error_type(logger_error)
        # Logging handlers may swallow I/O failures. An unconfirmed DB audit
        # must reach stderr regardless of the logger's return value.
        confirmed = context.get("audit_confirmed", False)
        if confirmed and logger_error_type is None:
            return
        emergency = {
            "event": "session.error.audit_unavailable",
            "operation_id": self.operation_id,
            "action": self.action,
            "stage": self.stage,
            "db_outcome": self.db_outcome,
            "audit_confirmed": confirmed,
            "error_type": _error_type(primary_error),
            "logger_error_type": logger_error_type,
        }
        try:
            await asyncio.to_thread(
                sys.stderr.write, json.dumps(emergency) + "\n",
            )
        except (Exception, asyncio.CancelledError) as output_error:
            BaseException.add_note(
                primary_error,
                "Session audit diagnostics unavailable "
                f"(operation_id={self.operation_id}, "
                f"output_error={_error_type(output_error)}).",
            )

    async def _finalize(
        self, db: AsyncSession, primary_error: BaseException,
    ) -> None:
        context: dict[str, Any] = {
            "operation_id": self.operation_id,
            "action": self.action,
            "user_id": self.user_id,
            "stage": self.stage,
            "db_outcome": self.db_outcome,
            "error": {"type": _error_type(primary_error)},
        }
        released = await self._release(db, context)
        try:
            context["error"] = _error_details(primary_error, self.error_code)
        except (Exception, asyncio.CancelledError) as context_error:
            context["context_error"] = {"type": _error_type(context_error)}

        confirmed = False
        if released:
            # A failed commit remains unknown even after a successful rollback.
            committed = self.db_outcome == "committed"
            account_id = self.account_id
            session_id = self.session_id
            if account_id is None and committed:
                account_id = self.new_account_id
            if session_id is None and committed:
                session_id = self.new_session_id
            try:
                await log_service.record_independent(
                    event="session.error", source="ext_api",
                    user_id=self.user_id, account_id=account_id,
                    session_id=session_id, context=context,
                )
                confirmed = True
            except (Exception, asyncio.CancelledError) as journal_error:
                context["error_journal_error"] = {
                    "type": _error_type(journal_error),
                }
        # Do not open another transaction if release could not be confirmed.
        context["transaction_released"] = released
        context["audit_confirmed"] = confirmed
        await self._emit(context, primary_error)

    async def report(
        self, db: AsyncSession, primary_error: BaseException,
    ) -> None:
        """Wait for audit completion before teardown on cancellation."""
        finalizer = asyncio.create_task(self._finalize(db, primary_error))
        cancellation: asyncio.CancelledError | None = None
        while True:
            try:
                await asyncio.shield(finalizer)
                break
            except asyncio.CancelledError as cancelled:
                if finalizer.cancelled():
                    current = asyncio.current_task()
                    if current is not None and current.cancelling():
                        cancellation = cancellation or cancelled
                    BaseException.add_note(
                        primary_error,
                        "Session error finalizer was cancelled "
                        f"(operation_id={self.operation_id}).",
                    )
                    break
                if cancellation is None:
                    cancellation = cancelled
            except Exception as finalizer_error:
                BaseException.add_note(
                    primary_error,
                    "Session error finalizer failed "
                    f"(operation_id={self.operation_id}, "
                    f"error_type={_error_type(finalizer_error)}).",
                )
                break
        if cancellation is not None:
            raise cancellation
