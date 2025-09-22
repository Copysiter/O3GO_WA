from secrets import token_urlsafe

from sqlalchemy import String, Boolean, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.adapters.db.base_class import Base


class User(Base):
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True
    )
    login: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True
    )
    hashed_password: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, unique=True
    )
    ext_api_key: Mapped[str] = mapped_column(
        String(64), nullable=False, default=lambda: token_urlsafe(32),
        index=True, unique=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False, default=True,
        server_default=text("True"), index=True
    )

    is_superuser: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False, default=False,
        server_default=text("False"), index=True
    )

    accounts = relationship("Account", back_populates="user")
