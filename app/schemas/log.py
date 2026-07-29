from typing import Any, List
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field

from app.crud.filter.sqlalchemy import Filter
from app.models.log import Log as LogModel
from app.schemas.account import Account, AccountFilter
from app.schemas.user import User


class LogBase(BaseModel):
    """Базовая схема записи событий."""
    event: str | None = Field(None, description="Название события")
    source: str | None = Field(None, description="Источник события")
    account_id: int | None = Field(None, description="ID аккаунта")
    session_id: int | None = Field(None, description="ID сессии")
    message_id: int | None = Field(None, description="ID сообщения")
    user_id: int | None = Field(None, description="ID пользователя")
    status: str | None = Field(None, description="Текущий статус")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Дополнительный контекст события"
    )
    created_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата создания события"
    )


class LogCreate(LogBase):
    """Схема для создания записи события."""
    event: str = Field(description="Название события")
    source: str = Field(description="Источник события")
    account_id: int = Field(description="ID аккаунта")
    status: str | int | None = Field(None, description="Текущий статус")


class LogUpdate(LogBase):
    """Схема для обновления записи события."""
    pass


class LogInDBBase(LogBase):
    """Базовая схема записи события с ID."""
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(None, description="Уникальный идентификатор")


class Log(LogInDBBase):
    """Схема записи события, возвращаемая из API."""
    account: Account | None = None
    user: User | None = None


class LogInDB(LogInDBBase):
    """Схема записи события, используемая внутри приложения."""
    pass


class LogList(BaseModel):
    """Схема списка записей событий с общим количеством."""
    data: List[Log]
    total: int = 0


class LogFilter(Filter):
    """Фильтр поиска записей событий."""
    id: int | None = None
    id__neq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    event: str | None = None
    event__neq: str | None = None
    event__in: list[str] | None = None
    event__ilike: str | None = None

    source: str | None = None
    source__neq: str | None = None
    source__in: list[str] | None = None

    account_id: int | None = None
    account_id__neq: int | None = None
    account_id__in: list[int] | None = None

    session_id: int | None = None
    session_id__neq: int | None = None
    session_id__in: list[int] | None = None
    session_id__isnull: bool | None = None

    message_id: int | None = None
    message_id__neq: int | None = None
    message_id__in: list[int] | None = None
    message_id__isnull: bool | None = None

    user_id: int | None = None
    user_id__neq: int | None = None
    user_id__in: list[int] | None = None
    user_id__isnull: bool | None = None

    status: str | None = None
    status__neq: str | None = None
    status__in: list[str] | None = None

    created_at: datetime | None = None
    created_at__gte: datetime | None = None
    created_at__lte: datetime | None = None

    account: AccountFilter | None = None

    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        model = LogModel
        ordering_field_name = "order_by"
