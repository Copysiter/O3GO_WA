from datetime import datetime
from enum import IntEnum

from sqlalchemy import (
    Integer, SmallInteger, String, ForeignKey, DateTime, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.adapters.db.base_class import Base
from .account import AccountStatus


class SessionStatus(IntEnum):
    BANNED    = -1
    FINISHED = 0
    ACTIVE    = 1
    PAUSED    = 2


class Session(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    account_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    ext_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True
    )
    status: Mapped[AccountStatus] = mapped_column(
        SmallInteger,
        default=AccountStatus.AVAILABLE, nullable=False, index=True
    )
    msg_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), nullable=False, index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), onupdate=func.now(),
        nullable=False, index=True
    )
    info_1: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_2: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_3: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_4: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_5: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_6: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_7: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )
    info_8: Mapped[str] = mapped_column(
        String(256), nullable=True, index=True
    )

    account = relationship(
        "Account", back_populates="sessions", lazy="selectin"
    )
    messages = relationship("Message", back_populates="session")
