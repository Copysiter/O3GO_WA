from typing import Optional

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas
from app.schemas.enum import MessageStatus


router = APIRouter()


@router.get(
    "/",
    response_model=schemas.MessageCreateResponse,
    status_code=status.HTTP_200_OK,
)
async def create_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    session_id: int = Query(..., description="ID сессии аккаунта"),
    number: str = Query(
        ..., max_length=64, description="Номер аккаунта-получателя"
    ),
    text: Optional[str] = Query(None, description="Текст сообщения"),
    info_1: Optional[str] = Query(
        None, max_length=256, description="Метаинформация 1"
    ),
    info_2: Optional[str] = Query(
        None, max_length=256, description="Метаинформация 2"\
            ),
    info_3: Optional[str] = Query(
        None, max_length=256, description="Метаинформация 3"
    ),
    status_: int = Query(
        MessageStatus.CREATED, description="Начальный статус сообщения"
    ),
    user: models.User = Depends(deps.get_user_by_api_key)
) -> schemas.MessageCreateResponse:
    """
    Создаёт сообщение.

    Принимает идентификатор сессии, номер получателя и опциональные поля
    (`text`, `info_1..3`). Поле `status_` необязательно; по умолчанию
    используется `MessageStatus.CREATED`.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        session_id: Идентификатор сессии-владельца сообщения.
        number: Номер получателя сообщения.
        text: Текст сообщения (опционально).
        info_1: Произвольная метка 1 (опционально).
        info_2: Произвольная метка 2 (опционально).
        info_3: Произвольная метка 3 (опционально).
        status_: Начальный статус сообщения (по умолчанию CREATED).
        user: Авторизованный пользователь (по API-ключу).

    Returns:
        MessageCreateResponse: Идентификатор созданного сообщения.

    Raises:
        HTTPException: 501 — функционал не реализован.
    """
    # TODO: реализовать создание сообщения (использовать CRUD, валидации и т.д.)
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get(
    "/status",
    response_model=schemas.MessageStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def update_message_status(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int = Query(..., description="ID сообщения"),
    status: int = Query(..., description="Новый статус сообщения"),
    user: models.User = Depends(deps.get_user_by_api_key)
) -> schemas.MessageStatusResponse:
    """
    Обновляет статус сообщения.

    Принимает `id` сообщения и новый `status_` (оба — через query-параметры).

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Идентификатор сообщения.
        status: Новый статус сообщения.
        user: Авторизованный пользователь (по API-ключу).

    Returns:
        MessageStatusOut: Подтверждение с `id` и текущим статусом.

    Raises:
        HTTPException:
            404 — если сообщение не найдено (после реализации логики);
            501 — функционал не реализован (сейчас).
    """
    # TODO: реализовать обновление статуса (поиск сообщения, проверка статуса, сохранение)
    raise HTTPException(status_code=501, detail="Not implemented")
