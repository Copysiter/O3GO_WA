from uuid import UUID
from typing import List
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from app.crud.filter.sqlalchemy import Filter
from app.models.account import Account as AccountModel, AccountStatus
from app.schemas.user import User


class AccountBase(BaseModel):
    """Базовая схема аккаунта с общими полями"""
    uuid: UUID | None = Field(
        None, description='UUID файла для скачивания'
    )
    user_id: int | None = Field(None, description="ID владельца кампании")
    number: str | None = Field(None, description="Номер аккаунта")
    type: int | None = Field(
        None, description="Тип аккаунта (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )
    file_name: str | None = Field(
        None, description='Название архива аккаунта'
    )
    profile_file_name: str | None = Field(
        None, description='Название файла с профилем'
    )
    limit: int | None = Field(
        -1, description='Лимит отправки сообщений подряд'
    )
    cooldown: int | None = Field(
        None, description='Пауза перед повторной отправкой сообщений'
    )
    session_count: int | None = Field(
        None, description="Исходное название архива"
    )
    status: int | None = Field(None, description="Статус аккаунта")
    created_at: datetime | None =  Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата добавления аккаунта"
    )
    updated_at: datetime | None = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Последняя дата использования"
    )
    geo: str | None = Field(None, description="Географическое положение")
    info_1: str | None = Field(None, description="Служебное поле 1")
    info_2: str | None = Field(None, description="Служебное поле 2")
    info_3: str | None = Field(None, description="Служебное поле 3")
    info_4: str | None = Field(None, description="Служебное поле 4")
    info_5: str | None = Field(None, description="Служебное поле 5")
    info_6: str | None = Field(None, description="Служебное поле 6")
    info_7: str | None = Field(None, description="Служебное поле 7")
    info_8: str | None = Field(None, description="Служебное поле 8")


class AccountUpload(BaseModel):
    """Базовая схема аккаунта с общими полями"""
    number: str = Field(description="Номер аккаунта")
    type: int | None = Field(
        None, description="Тип аккаунта (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )
    limit: int | None = Field(
        -1, description='Лимит отправки сообщений подряд'
    )
    cooldown: int | None = Field(
        None, description='Пауза перед повторной отправкой сообщений'
    )
    geo: str | None = Field(None, description="Географическое положение")
    info_1: str | None = Field(None, description="Служебное поле 1")
    info_2: str | None = Field(None, description="Служебное поле 2")
    info_3: str | None = Field(None, description="Служебное поле 3")
    info_4: str | None = Field(None, description="Служебное поле 4")
    info_5: str | None = Field(None, description="Служебное поле 5")
    info_6: str | None = Field(None, description="Служебное поле 6")
    info_7: str | None = Field(None, description="Служебное поле 7")
    info_8: str | None = Field(None, description="Служебное поле 8")


class AccountCreate(AccountBase):
    """Схема для создания нового аккаунта"""
    number: str | None = Field(None, description="Номер аккаунта")
    type: int | None = Field(
        None, description="Тип аккаунта (1 - WhatsApp, 2 - WhatsApp бизнес)"
    )
    status: int | None = Field(
        AccountStatus.AVAILABLE, description="Статус аккаунта"
    )


class AccountMultiCreate(AccountCreate):
    """Схема для создания новых аккаунтов при загрузке архивов"""
    files: List[str] = Field(description='Список названий файлов')
    user_id: int | None = Field(
        None, description='ID владельца аккаунта'
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
    download_url: str | None = Field(
        None, description="URL для скачивания архива"
    )
    profile_download_url: str | None = Field(
        None,description="URL для скачивания файла профиля"
    )


class AccountInDB(AccountInDBBase):
    """Схема аккаунта, используемая только внутри приложения"""
    pass


class AccountList(BaseModel):
    """Схема списка аккаунтов с общим количеством записей"""
    data: List[Account]
    total: int = 0


class AccountFilter(Filter):
    """Фильтр поиска аккаунтов по различным полям модели"""
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

    limit_at: int | None = None
    limit_at__gte: int | None = None
    limit_at__lte: int | None = None

    cooldown_at: int | None = None
    cooldown_at__gte: int | None = None
    cooldown_at__lte: int | None = None

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

    geo: str | None = None
    geo__neq: str | None = None
    geo__in: list[str] | None = None
    geo__ilike: str | None = None

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

    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        model = AccountModel

        # имя поля сортировки, совпадающий с атрибутом схемы
        ordering_field_name = "order_by"
