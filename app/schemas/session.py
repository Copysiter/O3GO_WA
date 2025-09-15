from typing import Optional, List
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict
from fastapi_filter.contrib.sqlalchemy import Filter

from app.schemas.enum import AccountStatus
from app.schemas.account import Account
from app.models.session import Session as SessionModel


class SessionBase(BaseModel):
    """Базовая схема сессии аккаунта с общими полями"""
    account_id: Optional[int] = Field(None, description="ID аккаунта")
    ext_id: Optional[str] = Field(None, description="Внешний ID сессии")
    msg_count: Optional[int] = Field(
        None, description="Количество отправленных сообщений"
    )
    status: Optional[int] = Field(None, description="Статус аккаунта")
    create_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата создания сессии аккаунта"
    )
    update_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата обновления сессии"
    )
    info_1: Optional[str] = Field(None, description="Служебное поле 1")
    info_2: Optional[str] = Field(None, description="Служебное поле 2")
    info_3: Optional[str] = Field(None, description="Служебное поле 3")


class SessionCreate(SessionBase):
    """Схема для создания нового сессии аккаунта"""
    account_id: int = Field(description="ID аккаунта")
    ext_id: str = Field(description="Внешний ID сессии")
    status: Optional[int] = Field(
        AccountStatus.AVAILABLE, description="Статус аккаунта"
    )


class SessionUpdate(SessionBase):
    """Схема для обновления существующего сессии аккаунта"""
    pass


class SessionInDBBase(SessionBase):
    """Базовая схема сессии аккаунта с ID, используемая при работе с БД"""
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(None, description="Уникальный идентификатор")


class Session(SessionInDBBase):
    """Схема сессии аккаунта, возвращаемая из API"""
    account: Account


class SessionInDB(SessionInDBBase):
    """Схема сессии аккаунта, используемая только внутри приложения"""
    pass


class SessionList(BaseModel):
    """Схема списка сессий аккаунтов с общим количеством записей"""
    data: List[Session]
    total: int = 0


class SessionFilter(Filter):
    """Фильтр для поиска сессии аккаунтов по различным полям модели"""
    id__eq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    account_id__eq: int | None = None
    account_id__in: list[int] | None = None

    status__eq: AccountStatus | None = None
    status__in: list[AccountStatus] | None = None

    msg_count__gt: int | None = None
    msg_count__lt: int | None = None

    created_at__eq: datetime | None = None
    created_at__gte: datetime | None = None
    created_at__lte: datetime | None = None

    updated_at__eq: datetime | None = None
    updated_at__gte: datetime | None = None
    updated_at__lte: datetime | None = None
    order_by: Optional[list[str]] = None

    class Constants(Filter.Constants):
        model = SessionModel
        ordering_field_name = "order_by"
