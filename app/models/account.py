import uuid
import logging

from datetime import datetime
from enum import IntEnum

from sqlalchemy import (
    Integer, SmallInteger, String, ForeignKey, DateTime, func, text
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.adapters.db.base_class import Base

logger = logging.getLogger(__name__)
logger.info("Account model loading - uuid module imported as uuid_module")


class AccountStatus(IntEnum):
    BANNED    = -1
    AVAILABLE = 0
    ACTIVE    = 1
    PAUSED    = 2


class Account(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    uuid: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, nullable=True, unique=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    type: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, index=True
    )
    geo: Mapped[str] = mapped_column(
        String(32), nullable=True, index=True
    )
    file_name: Mapped[str] = mapped_column(String, nullable=True, index=True)
    profile_file_name: Mapped[str] = mapped_column(
        String, nullable=True, index=True
    )
    limit: Mapped[int] = mapped_column(Integer, nullable=True)
    cooldown: Mapped[int] = mapped_column(Integer, nullable=True)
    status: Mapped[AccountStatus] = mapped_column(
        SmallInteger,
        default=AccountStatus.AVAILABLE, nullable=False, index=True
    )
    session_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
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

    user = relationship(
        "User", back_populates="accounts", lazy="selectin"
    )
    sessions = relationship(
        "Session", passive_deletes=True,back_populates="account"
    )
