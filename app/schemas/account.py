from typing import Optional, List
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict
from fastapi_filter.contrib.sqlalchemy import Filter

from app.schemas.enum import AccountStatus
from app.schemas.user import User
from app.models.account import Account as AccountModel


class AccountBase(BaseModel):
    """Базовая схема аккаунта с общими полями"""
    user_id: Optional[int] = Field(None, description="ID владельца кампании")
    number: Optional[str] = Field(None, description="Номер аккаунта")
    type: Optional[int] = Field(
        None, description="Тип аккаунта (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )
    session_count: Optional[int] = Field(
        None, description="Исходное название архива"
    )
    status: Optional[int] = Field(None, description="Статус аккаунта")
    created_at: Optional[datetime] =  Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата добавления аккаунта"
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Последняя дата использования"
    )
    info_1: Optional[str] = Field(None, description="Служебное поле 1")
    info_2: Optional[str] = Field(None, description="Служебное поле 2")
    info_3: Optional[str] = Field(None, description="Служебное поле 3")


class AccountCreate(AccountBase):
    """Схема для создания нового аккаунта"""
    number: Optional[str] = Field(None, description="Номер аккаунта")
    type: Optional[int] = Field(
        None, description="Тип аккаунта (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )
    status: Optional[int] = Field(
        AccountStatus.AVAILABLE, description="Статус аккаунта"
    )


class AccountUpdate(AccountBase):
    """Схема для обновления существующего аккаунта"""
    pass


class AccountInDBBase(AccountBase):
    """Базовая схема аккаунта с ID, используемая при работе с БД"""
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(None, description="Уникальный идентификатор")


class Account(AccountInDBBase):
    """Схема аккаунта, возвращаемая из API"""
    user: User


class AccountInDB(AccountInDBBase):
    """Схема аккаунта, используемая только внутри приложения"""
    pass


class AccountList(BaseModel):
    """Схема списка аккаунтов с общим количеством записей"""
    data: List[Account]
    total: int = 0


class AccountFilter(Filter):
    """Фильтр для поиска аккаунтов по различным полям модели"""
    id: int | None = None
    id__neq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    user_id: int | None = None
    user_id__neq: int | None = None
    user_id__in: list[int] | None = None

    type: int | None = None
    type__neq: int | None = None
    type__in: list[int] | None = None

    number: str | None = None
    number__neq: str | None = None
    number__in: list[str] | None = None
    number__ilike: str | None = None

    status: AccountStatus | None = None
    status__neq: AccountStatus | None = None
    status__in: list[AccountStatus] | None = None

    session_count: int | None = None
    session_count__neq: int | None = None
    session_count__gt: int | None = None
    session_count__lt: int | None = None

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

    order_by: Optional[list[str]] = None

    class Constants(Filter.Constants):
        model = AccountModel
        ordering_field_name = "order_by"
