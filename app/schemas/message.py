from typing import Optional, List
from datetime import datetime, timezone

from pydantic import BaseModel, Field, ConfigDict

from app.crud.filter.sqlalchemy import Filter
from app.models.message import Message as MessageModel, MessageStatus
from app.schemas.session import Session


class MessageBase(BaseModel):
    """Базовая схема сообщения с общими полями"""
    session_id: Optional[int] = Field(None, description="ID сессии аккаунта")
    number: Optional[str] = Field(None, description="Номер получателя")
    geo: Optional[str] = Field(
        None, description="Географическое положение аккаунта"
    )
    text: Optional[str] = Field(
        None, description="Тест сообщения"
    )
    status: Optional[int] = Field(None, description="Статус сообщения")
    created_at: Optional[datetime] =  Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата создания сообщения"
    )
    sent_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Дата отправки сообщения"
    )
    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Последняя дата изменения сообщения"
    )
    info_1: Optional[str] = Field(None, description="Служебное поле 1")
    info_2: Optional[str] = Field(None, description="Служебное поле 2")
    info_3: Optional[str] = Field(None, description="Служебное поле 3")
    info_4: Optional[str] = Field(None, description="Служебное поле 4")
    info_5: Optional[str] = Field(None, description="Служебное поле 5")
    info_6: Optional[str] = Field(None, description="Служебное поле 6")
    info_7: Optional[str] = Field(None, description="Служебное поле 7")
    info_8: Optional[str] = Field(None, description="Служебное поле 8")


class MessageCreate(MessageBase):
    """Схема для создания нового сообщения"""
    session_id: int = Field(description="ID сессии аккаунта")
    number: str = Field(description="Номер получателя")
    geo: str = Field(description="ТГеографическое положение аккаунта")
    status: Optional[int] = Field(
        MessageStatus.CREATED, description="Статус сообщения"
    )


class MessageUpdate(MessageBase):
    """Схема для обновления существующего сообщения"""
    pass


class MessageInDBBase(MessageBase):
    """Базовая схема сообщения с ID, используемая при работе с БД"""
    model_config = ConfigDict(from_attributes=True)
    id: int = Field(None, description="Уникальный идентификатор")


class Message(MessageInDBBase):
    """Схема сообщения, возвращаемая из API"""
    session: Session


class MessageInDB(MessageInDBBase):
    """Схема сообщения, используемая только внутри приложения"""
    pass


class MessageList(BaseModel):
    """Схема списка сообщений с общим количеством записей"""
    data: List[Message]
    total: int = 0


class MessageFilter(Filter):
    """Фильтр поиска сообщений по различным полям модели"""
    id: int | None = None
    id__neq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    session_id: int | None = None
    session_id__neq: list[int] | None = None
    session_id__in: list[int] | None = None

    number: str | None = None
    number__neq: str | None = None
    number__in: list[str] | None = None
    number__ilike: str | None = None

    geo: str | None = None
    geo__neq: str | None = None
    geo__in: list[str] | None = None
    geo__ilike: str | None = None

    status: MessageStatus | None = None
    status__neq: list[MessageStatus] | None = None
    status__in: list[MessageStatus] | None = None

    created_at: datetime | None = None
    created_at__gte: datetime | None = None
    created_at__lte: datetime | None = None

    sent_at: datetime | None = None
    sent_at__gte: datetime | None = None
    sent_at__lte: datetime | None = None

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
        model = MessageModel
        ordering_field_name = "order_by"


class MessageCreateResponse(BaseModel):
    """Ответ при создании сообщения."""
    id: int = Field(..., description="ID созданного сообщения")


class MessageStatusResponse(MessageCreateResponse):
    """Ответ при обновлении статуса сообщения."""
    status: str = Field(..., description="Текущий статус сообщения")
