from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime, ForeignKey, Integer, String, func, text
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.adapters.db.base_class import Base


class Log(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    message_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("message.id", ondelete="CASCADE"),
        nullable=True, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=True, index=True
    )
    context: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), nullable=False, index=True
    )

    account = relationship("Account", lazy="selectin")
    session = relationship("Session", lazy="selectin")
    message = relationship("Message", lazy="selectin")
    user = relationship("User", lazy="selectin")
