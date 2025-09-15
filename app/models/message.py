from datetime import datetime

from sqlalchemy import (
    Column, Integer, SmallInteger, String, Text, ForeignKey, DateTime, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship


from app.adapters.db.base_class import Base
from app.schemas.enum import MessageStatus


class Message(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("session.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True
    )
    geo: Mapped[str] = mapped_column(
        String(64), index=True
    )
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[MessageStatus] = mapped_column(
        SmallInteger,
        default=MessageStatus.CREATED, nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(), nullable=False, index=True
    )
    sent_at: Mapped[datetime] = mapped_column(
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

    session = relationship("Session", back_populates="messages")
