"""Pydantic schemas for external message API."""
from pydantic import BaseModel, Field


class GetNextMessageResponse(BaseModel):
    """Response from GET /ext/api/v1/messages/next."""
    id: int = Field(..., description="ID сообщения")
    phone: str = Field(..., description="Номер телефона")
    text: str = Field(..., description="Текст сообщения")
    follow: int = Field(..., description="Флаг отслеживания")


class SetMessageStatusResponse(BaseModel):
    """Response from GET /ext/api/v1/messages/status."""
    id: int = Field(..., description="ID сообщения")
    dst_addr: str = Field(..., description="Адрес получателя")
    src_addr: str = Field(..., description="Адрес отправителя")
    text: str = Field(..., description="Текст сообщения")
    status: str = Field(..., description="Статус сообщения")