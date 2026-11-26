"""Retain account history while removing archived account files.

ARCHIVED plus non-NULL filenames is the durable retry queue. Never clear a
reference until unlink succeeds (or the file is already missing/shared).
"""
import asyncio
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select, update, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Session
from app.models.account import AccountStatus
from app.models.session import SessionStatus
from app.services.log import LogOperation, log_service

UPLOAD_DIR = Path("upload/wa")
PROFILE_UPLOAD_DIR = Path("upload/wa/profile")


def unlink_file(directory: Path, name: str) -> bool:
    """Reject traversal and symlinks; never follow a path outside our root."""
    if not name or Path(name).name != name or name in (".", ".."):
        raise ValueError("Unsafe account filename")
    path = directory / name
    if path.is_symlink() or path.resolve().parent != directory.resolve():
        raise ValueError("Unsafe account file path")
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True


async def lock_account(db: AsyncSession, account_id: int) -> Account | None:
    return (await db.execute(
        select(Account).where(Account.id == account_id)
        .with_for_update().execution_options(populate_existing=True)
    )).scalar_one_or_none()


async def cleanup_archived_files(
    db: AsyncSession, account_id: int, *, source: str = "ext_api",
) -> bool:
    """Commit each file independently; leave failed references for retry."""
    complete = True
    for column_name, directory, kind in (
        ("file_name", UPLOAD_DIR, "archive"),
        ("profile_file_name", PROFILE_UPLOAD_DIR, "profile"),
    ):
        name = None
        owner_id = None
        operation_id = str(uuid4())
        try:
            account = await lock_account(db, account_id)
            if account is None or account.status != AccountStatus.ARCHIVED:
                await db.rollback()
                return False
            owner_id = account.user_id
            name = getattr(account, column_name)
            if not name:
                if name is not None:
                    await db.execute(update(Account).where(Account.id == account_id).values(
                        **{column_name: None}, updated_at=Account.updated_at,
                    ))
                await db.commit()
                continue
            column = getattr(Account, column_name)
            shared = bool(await db.scalar(select(
                select(Account.id).where(
                    Account.id != account_id, column == name,
                ).exists()
            )))
            deleted = False
            if not shared:
                deleted = await asyncio.to_thread(unlink_file, directory, name)
            await db.execute(update(Account).where(Account.id == account_id).values(
                **{column_name: None}, updated_at=Account.updated_at,
            ))
            await log_service.record(
                db, event="account.file.delete", source=source,
                account_id=account_id, user_id=owner_id,
                context={"operation_id": operation_id,
                         "file_kind": kind, "file_name": name,
                         "reason": "archived", "deleted": deleted,
                         "shared": shared}, commit=False,
            )
            await db.commit()
        except asyncio.CancelledError:
            await db.rollback()
            raise
        except Exception as error:
            complete = False
            await db.rollback()
            # An audit failure must not prevent retries or the other file.
            try:
                await log_service.record(
                    db, event="account.file.delete.error", source=source,
                    account_id=account_id, user_id=owner_id,
                    context={"operation_id": operation_id,
                             "file_kind": kind, "file_name": name,
                             "reason": "archived", "error_type": type(error).__name__},
                    commit=True,
                )
            except Exception:
                await db.rollback()
    return complete


async def archive_session_account(
    db: AsyncSession, *, session_id: int, user_id: int, number: str,
    info: dict[str, str], audit: LogOperation | None = None,
) -> None:
    """Serialize against start/finish/upload and reject stale confirmations."""
    current = await db.get(Session, session_id)
    if current is None:
        raise HTTPException(404, "Session not found")
    account = await lock_account(db, current.account_id)
    if account is None or account.user_id != user_id:
        raise HTTPException(404, "Session not found")
    if account.number != number:
        raise HTTPException(400, "Account mismatch for provided session id and number")
    await db.refresh(current)
    latest_id = await db.scalar(
        select(Session.id).where(Session.account_id == account.id)
        .order_by(Session.id.desc()).limit(1)
    )
    if latest_id != current.id:
        raise HTTPException(409, "Stale session cannot archive account")
    if account.status == AccountStatus.ARCHIVED:
        if current.status != SessionStatus.BANNED:
            raise HTTPException(409, "Account is archived")
        await db.commit()
        return
    if current.status == SessionStatus.BANNED and account.status != AccountStatus.BANNED:
        raise HTTPException(409, "Account has been acquired after this ban")
    if current.status not in (SessionStatus.ACTIVE, SessionStatus.BANNED):
        raise HTTPException(409, "Session is not active or banned")
    if current.status != SessionStatus.BANNED:
        await log_service.record(
            db, event="session.status", source="ext_api",
            account_id=account.id, session_id=current.id, user_id=user_id,
            status=SessionStatus.BANNED,
        )
    if account.status != AccountStatus.BANNED:
        await log_service.record(
            db, event="account.status", source="ext_api",
            account_id=account.id, session_id=current.id, user_id=user_id,
            status=AccountStatus.BANNED,
        )
    current.status = SessionStatus.BANNED
    account.status = AccountStatus.ARCHIVED
    for field, value in info.items():
        setattr(current, field, value)
        setattr(account, field, value)
    await db.flush()
    await log_service.record(
        db, event="account.status", source="ext_api",
        account_id=account.id, session_id=current.id, user_id=user_id,
        status=AccountStatus.ARCHIVED,
        context={"reason": "confirmed_ban", "file_name": account.file_name,
                 "profile_file_name": account.profile_file_name},
    )
    if audit is not None:
        audit.stage = "commit"
        audit.db_outcome = "unknown"
    await db.commit()
    if audit is not None:
        audit.db_outcome = "committed"


async def retry_archived_files(db: AsyncSession) -> None:
    ids = list((await db.scalars(select(Account.id).where(
        Account.status == AccountStatus.ARCHIVED,
        or_(Account.file_name.is_not(None), Account.profile_file_name.is_not(None)),
    ).order_by(Account.id))).all())
    await db.commit()
    for account_id in ids:
        await cleanup_archived_files(db, account_id, source="scheduler")
