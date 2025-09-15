from datetime import datetime

from sqlalchemy import (
    Column, Integer, SmallInteger, String, ForeignKey, DateTime, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.adapters.db.base_class import Base
from app.schemas.enum import AccountStatus


class Account(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True
    )
    type: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=1, index=True
    )
    status: Mapped[AccountStatus] = mapped_column(
        SmallInteger,
        default=AccountStatus.AVAILABLE, nullable=False, index=True
    )
    session_count: Mapped[int] = mapped_column(
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
    info_1 = Column(String(256), nullable=True, index=True)
    info_2 = Column(String(256), nullable=True, index=True)
    info_3 = Column(String(256), nullable=True, index=True)

    user = relationship("User", back_populates="accounts")
    sessions = relationship("Session", back_populates="account")
