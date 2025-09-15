from typing import Any

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas


router = APIRouter()


@router.get(
    "/start",
    response_model=schemas.SessionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def start_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: str = Query(..., description="Внешний ID сессии"),
    number: str = Query(
        ..., max_length=64, description="Номер аккаунта/получателя"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """
    Помечает сессию как запущенную.

    Принимает идентификатор сессии и номер. Авторизация — по API-ключу.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Внешний идентификатор сессии.
        number: Номер аккаунта.
        user: Авторизованный пользователь (по API-ключу).

    Returns:
        SessionStatusResponse: Подтверждение с `id`, `number` и `status`.

    Raises:
        HTTPException: 501 — функционал не реализован.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get(
    "/finish",
    response_model=schemas.SessionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def finish_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: str = Query(..., description="Внешний ID сессии"),
    number: str = Query(
        ..., max_length=64, description="Номер аккаунта"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """
    Помечает сессию как завершённую.

    Принимает идентификатор сессии и номер. Авторизация — по API-ключу.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Внешний идентификатор сессии.
        number: Номер аккаунта.
        user: Авторизованный пользователь (по API-ключу).

    Returns:
        SessionStatusOut: Подтверждение с `session_id`, `number` и `status`.

    Raises:
        HTTPException: 501 — функционал не реализован.
    """
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get(
    "/ban",
    response_model=schemas.SessionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def ban_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: str = Query(..., description="Внешний ID сессии"),
    number: str = Query(
        ..., max_length=64, description="Номер аккаунта"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """
    Помечает сессию как заблокированную.

    Принимает идентификатор сессии и номер. Авторизация — по API-ключу.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Внешний идентификатор сессии.
        number: Номер аккаунта.
        user: Авторизованный пользователь (по API-ключу).

    Returns:
        SessionStatusOut: Подтверждение с `session_id`, `number` и `status`.

    Raises:
        HTTPException: 501 — функционал не реализован.
    """
    raise HTTPException(status_code=501, detail="Not implemented")
