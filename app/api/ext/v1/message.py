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
    number: str = Query(..., max_length=64, description="Номер аккаунта-получателя"),
    text: Optional[str] = Query(None, description="Текст сообщения"),
    info_1: Optional[str] = Query(None, max_length=256, description="Метаинформация 1"),
    info_2: Optional[str] = Query(None, max_length=256, description="Метаинформация 2"),
    info_3: Optional[str] = Query(None, max_length=256, description="Метаинформация 3"),
) -> schemas.MessageCreateResponse:
    """Создаёт новое сообщение, привязанное к сессии."""
    db_session = await crud.session.get(db, session_id)
    if not db_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with id={session_id} not found",
        )

    msg_obj = schemas.MessageCreate(
        session_id=session_id,
        number=number,
        geo="",
        text=text or "",
        status=MessageStatus.CREATED,
        info_1=info_1,
        info_2=info_2,
        info_3=info_3,
    )

    created = await crud.message.create(db=db, obj_in=msg_obj)
    return schemas.MessageCreateResponse(id=created.id)


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
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.MessageStatusResponse:
    """Обновляет статус сообщения."""
    db_obj = await crud.message.get(db, id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message with id={id} not found",
        )

    if MessageStatus.name(status) is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid message status: {status}",
        )

    updated = await crud.message.update(db, db_obj=db_obj, obj_in={"status": status})
    return schemas.MessageStatusResponse(id=updated.id, status=updated.status)
