from typing import Optional, Literal

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.sync import update
from sqlalchemy import column

from app.core.logger import logger, E

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas

from app.models.message import MessageStatus
from app.utils.geo import get_geo_by_number


router = APIRouter()


@router.get(
    "/",
    response_model=schemas.MessageCreateResponse,
    status_code=status.HTTP_200_OK,
)
async def create_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    session_id: Optional[int] = Query(None, description="ID сессии аккаунта"),
    session_ext_id: Optional[str] = Query(
        None, description="Внешний ID сессии аккаунта"
    ),
    number: Optional[str] = Query(
        None, max_length=64, description="Номер аккаунта-получателя"
    ),
    text: Optional[str] = Query(None, description="Текст сообщения"),
    info_1: Optional[str] = Query(
        None, max_length=256, description="Служебное инфо поле 1"
    ),
    info_2: Optional[str] = Query(
        None, max_length=256, description="Служебное инфо поле 2"
    ),
    info_3: Optional[str] = Query(
        None, max_length=256, description="Служебное инфо поле 3"
    ),
    user: models.User = Depends(deps.get_user_by_api_key)
) -> schemas.MessageCreateResponse:
    """Создаёт новое сообщение, привязанное к сессии."""
    try:
        if session_id:
            session = await crud.session.get(db, session_id)
        elif session_ext_id:
            session = await crud.session.get_by(db, ext_id=session_ext_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Missing required field: 'session_id' or 'session_ext_id'."
            )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with id={session_id} not found",
            )

        await crud.session.update(
            db, id=session.id, obj_in={'msg_count': column('msg_count') + 1}
        )

        obj_in = schemas.MessageCreate(
            session_id=session.id,
            number=number if number else session.account.number,
            geo=get_geo_by_number(number),
            text=text,  # если не передан, сохранится NULL
            status=MessageStatus.CREATED,
            info_1=info_1,
            info_2=info_2,
            info_3=info_3
        )

        message = await crud.message.create(db=db, obj_in=obj_in)

        return schemas.MessageCreateResponse(id=message.id)
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.get(
    "/status",
    response_model=schemas.MessageStatusResponse,
    status_code=status.HTTP_200_OK
)
async def update_message_status(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int = Query(..., description="ID сообщения"),
    status: Literal[
        'waiting', 'sent', 'delivered', 'undelivered', 'failed'
    ] = Query(..., description="Новый статус сообщения"),
    info_1: Optional[str] = Query(
        None, max_length=256, description="Служебное инфо поле 1"
    ),
    info_2: Optional[str] = Query(
        None, max_length=256, description="Служебное инфо поле 2"
    ),
    info_3: Optional[str] = Query(
        None, max_length=256, description="Служебное инфо поле 3"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.MessageStatusResponse:
    """Обновляет статус сообщения."""
    try:
        message = await crud.message.get(db, id)
        if not message or message.session.account.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Message with id={id} not found",
            )
        new_status = getattr(
            schemas.MessageStatus, status.upper(), message.status
        )
        obj_in = schemas.MessageUpdate(status=new_status)
        for info in ['info_1', 'info_2', 'info_3']:
            if locals()[info] is not None:
                setattr(obj_in, info, locals()[info])
        message = await crud.message.update(
            db, db_obj=message, obj_in=obj_in
        )

        return schemas.MessageStatusResponse(
            id=message.id,
            status=schemas.MessageStatus(message.status).name.lower()
        )
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
