from typing import Optional, List
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from app.crud.filter.sqlalchemy import Filter
from app.models.session import Session as SessionModel, AccountStatus
from app.schemas.account import Account


class SessionBase(BaseModel):
    """Базовая схема сессии аккаунта с общими полями"""
    account_id: Optional[int] = Field(None, description="ID аккаунта")
    ext_id: Optional[str] = Field(None, description="Внешний ID сессии")
    msg_count: Optional[int] = Field(
        None, description="Количество отправленных сообщений"
    )
    status: Optional[int] = Field(None, description="Статус аккаунта")
    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата создания сессии аккаунта"
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата обновления сессии"
    )
    info_1: Optional[str] = Field(None, description="Служебное поле 1")
    info_2: Optional[str] = Field(None, description="Служебное поле 2")
    info_3: Optional[str] = Field(None, description="Служебное поле 3")
    info_4: Optional[str] = Field(None, description="Служебное поле 4")
    info_5: Optional[str] = Field(None, description="Служебное поле 5")
    info_6: Optional[str] = Field(None, description="Служебное поле 6")
    info_7: Optional[str] = Field(None, description="Служебное поле 7")
    info_8: Optional[str] = Field(None, description="Служебное поле 8")


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
    """Фильтр поиска сессии аккаунтов по различным полям модели"""
    id: int | None = None
    id__neq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    ext_id: str | None = None
    ext_id__neq: str | None = None
    ext_id__in: list[str] | None = None
    ext_id__ilike: str | None = None

    account_id: int | None = None
    account_id__neq: int | None = None
    account_id__in: list[int] | None = None

    status: AccountStatus | None = None
    status__neq: AccountStatus | None = None
    status__in: list[AccountStatus] | None = None

    msg_count: int | None = None
    msg_count__neq: int | None = None
    msg_count__gt: int | None = None
    msg_count__lt: int | None = None

    created_at: datetime | None = None
    created_at__gte: datetime | None = None
    created_at__lte: datetime | None = None

    updated_at: datetime | None = None
    updated_at__gte: datetime | None = None
    updated_at__lte: datetime | None = None

    info_1: str | None = None
    info_1__neq: str | None = None
    info_1__in: list[str] | None = None
    info_1__ilike: str | None = None

    info_2: str | None = None
    info_2__neq: str | None = None
    info_2__in: list[str] | None = None
    info_2__ilike: str | None = None

    info_3: str | None = None
    info_3__neq: str | None = None
    info_3__in: list[str] | None = None
    info_3__ilike: str | None = None

    info_4: str | None = None
    info_4__neq: str | None = None
    info_4__in: list[str] | None = None
    info_4__ilike: str | None = None

    info_5: str | None = None
    info_5__neq: str | None = None
    info_5__in: list[str] | None = None
    info_5__ilike: str | None = None

    info_6: str | None = None
    info_6__neq: str | None = None
    info_6__in: list[str] | None = None
    info_6__ilike: str | None = None

    info_7: str | None = None
    info_7__neq: str | None = None
    info_7__in: list[str] | None = None
    info_7__ilike: str | None = None

    info_8: str | None = None
    info_8__neq: str | None = None
    info_8__in: list[str] | None = None
    info_8__ilike: str | None = None

    order_by: Optional[list[str]] = None

    class Constants(Filter.Constants):
        model = SessionModel
        ordering_field_name = "order_by"


class SessionStatusResponse(BaseModel):
    """Ответ при изменении статуса сессии аккаунта."""
    id: int = Field(..., description="Идентификатор сессии")
    ext_id: str = Field(..., description="Внешний идентификатор сессии")
    number: str = Field(..., description="Номер аккаунта")
    status: str = Field(..., description="Текущий статус сессии аккаунта")
