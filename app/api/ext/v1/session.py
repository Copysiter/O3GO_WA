from typing import Any

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas
from app.schemas.enum import AccountStatus

router = APIRouter()


async def _update_session_status(
    db: AsyncSession,
    id: str,
    user_id: str,
    number: str,
    status: AccountStatus,
    msg_count: int = 0,
) -> schemas.SessionStatusResponse:
    """Обновляет статус сессии, проверяя связанный аккаунт, и увеличивает msg_count при необходимости."""
    session = await crud.session.get_by(db, ext_id=id)
    if not session or session.account.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ext_id={id} not found",
        )

    account = await crud.account.get(db, session.account_id)
    if not account or account.number != number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account mismatch for provided session id and number",
        )

    update_data = {"status": status}
    if msg_count > 0:
        update_data["msg_count"] = session.msg_count + msg_count

    session = await crud.session.update(db, db_obj=session, obj_in=update_data)

    return schemas.SessionStatusResponse(
        id=session.ext_id,
        number=account.number,
        status=session.status,
        msg_count=session.msg_count,
    )


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
    Стартует сессию:
    если аккаунта нет — создаёт, если сессия уже существует — ошибка.
    """

    # Проверяем, нет ли уже сессии с таким ext_id
    existing = await crud.session.get_by(db, ext_id=id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session with ext_id={id} already exists",
        )

    # Проверяем аккаунт, если нет — создаём
    account = await crud.account.get_by(db, number=number)
    if not account:
        obj_in = schemas.AccountCreate(number=number, user_id=user.id)
        account = await crud.account.create(db=db, obj_in=obj_in)

    # Создаём новую сессию
    obj_in = schemas.SessionCreate(
        account_id=account.id, ext_id=id, status=AccountStatus.ACTIVE
    )
    session = await crud.session.create(db=db, obj_in=obj_in)

    return schemas.SessionStatusResponse(
        id=session.ext_id,
        number=account.number,
        status=session.status,
        msg_count=session.msg_count,
    )


@router.get(
    "/finish",
    response_model=schemas.SessionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def finish_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: str = Query(..., description="Внешний ID сессии"),
    number: str = Query(..., max_length=64, description="Номер аккаунта"),
    msg_count: int = Query(
        0, ge=0, description="Количество сообщений, которое нужно прибавить"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как завершённую (AVAILABLE) и обновляет msg_count."""
    return await _update_session_status(
        db, id=id, user_id=user.id, number=number,
        status=AccountStatus.AVAILABLE, msg_count=msg_count
    )


@router.get(
    "/ban",
    response_model=schemas.SessionStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def ban_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: str = Query(..., description="Внешний ID сессии"),
    number: str = Query(..., max_length=64, description="Номер аккаунта"),
    msg_count: int = Query(
        0, ge=0, description="Количество сообщений, которое нужно прибавить"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как заблокированную (BANNED) и обновляет msg_count."""
    return await _update_session_status(
        db, id=id, user_id=user.id, number=number,
        status=AccountStatus.BANNED, msg_count=msg_count
    )
