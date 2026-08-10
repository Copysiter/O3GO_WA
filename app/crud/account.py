from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crud.base import CRUDBase
from app.models.account import Account
from app.models.message import Message, MessageStatus
from app.models.session import Session, SessionStatus
from app.schemas.account import AccountCreate, AccountUpdate, AccountFilter


class AccountCRUD(
    CRUDBase[Account, AccountCreate, AccountUpdate, AccountFilter]
):
    """CRUD-репозиторий для Account с поддержкой фильтра AccountFilter."""

    def __init__(self) -> None:
        super().__init__(model=Account, filter_class=AccountFilter)

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

        current_session_id = (
            select(Session.id)
            .where(
                Session.account_id == account_id,
                Session.status == SessionStatus.ACTIVE
            )
            .order_by(Session.id.desc())
            .limit(1)
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


account = AccountCRUD()
