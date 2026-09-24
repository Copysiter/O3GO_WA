from typing import Any, Sequence

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.account import Account, AccountStatus
from app.models.message import Message, MessageStatus
from app.models.session import Session, SessionStatus
from app.schemas.account import AccountCreate, AccountUpdate, AccountFilter


class AccountCRUD(
    CRUDBase[Account, AccountCreate, AccountUpdate, AccountFilter]
):
    """CRUD-репозиторий для Account с поддержкой фильтра AccountFilter."""

    def __init__(self) -> None:
        super().__init__(model=Account, filter_class=AccountFilter)

    async def list_archive_files(
        self,
        db: AsyncSession,
        *,
        before_id: int | None = None,
        limit: int = 1000
    ) -> Sequence[tuple[int, str]]:
        """Возвращает порцию ID и непустых имён архивов по убыванию ID."""
        stmt = select(Account.id, Account.file_name).where(
            Account.file_name.is_not(None),
            Account.file_name != ""
        )
        if before_id is not None:
            stmt = stmt.where(Account.id < before_id)
        stmt = stmt.order_by(Account.id.desc()).limit(limit)

        result = await db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_owned_by_id(
        self,
        db: AsyncSession,
        *,
        account_id: int,
        user_id: int
    ) -> Account | None:
        """Возвращает аккаунт владельца по ID."""
        stmt = select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def list_owned_by_number(
        self,
        db: AsyncSession,
        *,
        number: str,
        user_id: int
    ) -> Sequence[Account]:
        """Возвращает не более двух аккаунтов владельца с данным номером."""
        stmt = (
            select(Account)
            .where(Account.number == number, Account.user_id == user_id)
            .order_by(Account.id.asc())
            .limit(2)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def list_with_active_session_device(
        self,
        db: AsyncSession,
        *,
        filter: AccountFilter | dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100
    ) -> Sequence[tuple[Account, str | None]]:
        """Возвращает аккаунты с device последней активной сессии."""
        active_session_device = (
            select(Session.device)
            .where(
                Session.account_id == Account.id,
                Session.status == SessionStatus.ACTIVE
            )
            .order_by(Session.id.desc())
            .limit(1)
            .correlate(Account)
            .scalar_subquery()
        )
        f = self._get_filter(filter)
        stmt = select(
            Account,
            active_session_device.label("device")
        )
        if f is not None:
            stmt = f.filter(stmt)
            stmt = f.sort(stmt)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]

    async def get_report_summary(
        self,
        db: AsyncSession,
        *,
        account_id: int,
        owner_user_id: int | None = None
    ) -> tuple[Account, dict[str, Any]] | None:
        """Возвращает аккаунт и агрегаты для его детальной страницы."""
        account_stmt = select(Account).where(Account.id == account_id)
        if owner_user_id is not None:
            account_stmt = account_stmt.where(Account.user_id == owner_user_id)

        account_result = await db.execute(account_stmt)
        account = account_result.scalar_one_or_none()
        if account is None:
            return None

        current_session = (
            select(
                Session.id.label("id"),
                Session.device.label("device")
            )
            .where(
                Session.account_id == account_id,
                Session.status == SessionStatus.ACTIVE
            )
            .order_by(Session.id.desc())
            .limit(1)
            .cte("current_session")
        )
        current_session_id = (
            select(current_session.c.id)
            .scalar_subquery()
        )
        current_session_device = (
            select(current_session.c.device)
            .scalar_subquery()
        )
        session_count = (
            select(func.count(Session.id))
            .where(Session.account_id == account_id)
            .scalar_subquery()
        )
        terminal_statuses = (
            MessageStatus.DELIVERED,
            MessageStatus.UNDELIVERED,
            MessageStatus.FAILED,
        )
        stats_stmt = (
            select(
                session_count.label("session_count"),
                current_session_id.label("current_session_id"),
                current_session_device.label("device"),
                func.count(Message.id).label("message_count_total"),
                func.count(Message.id).filter(
                    Message.session_id == current_session_id
                ).label("message_count_current"),
                func.count(Message.id).filter(
                    Message.status == MessageStatus.DELIVERED
                ).label("delivery_all_delivered"),
                func.count(Message.id).filter(
                    Message.status.in_(terminal_statuses)
                ).label("delivery_all_terminal"),
                func.count(Message.id).filter(
                    Message.session_id == current_session_id,
                    Message.status == MessageStatus.DELIVERED
                ).label("delivery_current_delivered"),
                func.count(Message.id).filter(
                    Message.session_id == current_session_id,
                    Message.status.in_(terminal_statuses)
                ).label("delivery_current_terminal"),
            )
            .select_from(Message)
            .join(Session, Message.session_id == Session.id)
            .where(Session.account_id == account_id)
        )
        stats_result = await db.execute(stats_stmt)
        return account, dict(stats_result.one()._mapping)

    async def update_hash(
        self,
        db: AsyncSession,
        *,
        account_id: int,
        user_id: int,
        value: str | None,
        commit: bool = False
    ) -> Account | None:
        """Изменяет hash и освобождает аккаунт без смены updated_at."""
        stmt = (
            update(Account)
            .where(
                Account.id == account_id,
                Account.user_id == user_id
            )
            .values(
                hash=value,
                status=AccountStatus.AVAILABLE,
                updated_at=Account.updated_at
            )
            .returning(Account)
            .execution_options(populate_existing=True)
        )
        result = await db.execute(stmt)
        account = result.scalar_one_or_none()

        if account is not None and commit:
            await db.commit()

        return account


account = AccountCRUD()
