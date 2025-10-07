from typing import Optional

from fastapi import (
    APIRouter, Query, Depends, HTTPException, status as http_status
)
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas
from app.schemas.enum import AccountStatus, SessionStatus


router = APIRouter()


async def _update_session_status(
    db: AsyncSession,
    id: Optional[int] = None,
    ext_id: Optional[str] = None,
    *,
    user_id: str,
    number: str,
    status: AccountStatus,
    msg_count: int = 0,
) -> schemas.SessionStatusResponse:
    """Обновляет статус сессии, проверяя связанный аккаунт, и увеличивает msg_count при необходимости."""
    if id:
        session = await crud.session.get(db, id)
    elif ext_id:
        session = await crud.session.get_by(db, ext_id=ext_id)
    else:
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required field: 'session_id' or 'session_ext_id'."
        )
    if not session or session.account.user_id != user_id:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Session not found",
        )

    account = await crud.account.get(db, session.account_id)
    if not account or account.number != number:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Account mismatch for provided session id and number",
        )

    obj_in = schemas.SessionUpdate(status=status)
    if msg_count > 0:
        obj_in.msg_count = session.msg_count + msg_count

    session = await crud.session.update(db, db_obj=session, obj_in=obj_in)
    account = await crud.session.update(
        db, db_obj=account, obj_in=schemas.SessionUpdate(status=status)
    )

    return schemas.SessionStatusResponse(
        id=session.id,
        ext_id=session.ext_id,
        number=account.number,
        status=SessionStatus(session.status).name.lower(),
        msg_count=session.msg_count,
    )


@router.get(
    "/start",
    response_model=schemas.SessionStatusResponse,
    status_code=http_status.HTTP_200_OK,
)
async def start_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    ext_id: str = Query(..., description="Внешний ID сессии"),
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
    existing = await crud.session.get_by(db, ext_id=ext_id)
    if existing:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Session with ext_id={ext_id} already exists",
        )

    # Проверяем аккаунт, если нет — создаём
    account = await crud.account.get_by(db, number=number)
    if account:
        account = await crud.account.update(
            db, db_obj=account,
            obj_in=schemas.AccountUpdate(status=AccountStatus.ACTIVE)
        )
        await crud.session.update(
            db, obj_in=schemas.SessionUpdate(status=SessionStatus.FINISHED),
            filter={
                "account_id": account.id,
                "status__in": [SessionStatus.ACTIVE, SessionStatus.PAUSED]
            }
        )
    else:
        account = await crud.account.create(
            db=db, obj_in=schemas.AccountCreate(
                number=number, user_id=user.id, status=AccountStatus.ACTIVE
            )
        )

    # Создаём новую сессию
    session = await crud.session.create(
        db=db, obj_in=schemas.SessionCreate(
            account_id=account.id, ext_id=ext_id, status=AccountStatus.ACTIVE
        )
    )

    return schemas.SessionStatusResponse(
        id=session.id,
        ext_id=session.ext_id,
        number=account.number,
        status=SessionStatus(session.status).name.lower(),
        msg_count=session.msg_count,
    )


@router.get(
    "/finish",
    response_model=schemas.SessionStatusResponse,
    status_code=http_status.HTTP_200_OK,
)
async def finish_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: Optional[int] = Query(None, description="ID сессии аккаунта"),
    ext_id: Optional[str] = Query(
        None, description="Внешний ID сессии аккаунта"
    ),
    number: str = Query(..., max_length=64, description="Номер аккаунта"),
    msg_count: int = Query(
        0, ge=0, description="Количество сообщений, которое нужно прибавить"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как завершённую (AVAILABLE) и обновляет msg_count."""
    return await _update_session_status(
        db, id=id, ext_id=ext_id, user_id=user.id, number=number,
        status=AccountStatus.AVAILABLE, msg_count=msg_count
    )


@router.get(
    "/ban",
    response_model=schemas.SessionStatusResponse,
    status_code=http_status.HTTP_200_OK,
)
async def ban_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: Optional[int] = Query(None, description="ID сессии аккаунта"),
    ext_id: Optional[str] = Query(
        None, description="Внешний ID сессии аккаунта"
    ),
    number: str = Query(..., max_length=64, description="Номер аккаунта"),
    msg_count: int = Query(
        0, ge=0, description="Количество сообщений, которое нужно прибавить"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как заблокированную (BANNED) и обновляет msg_count."""
    return await _update_session_status(
        db, id=id, ext_id=ext_id, user_id=user.id, number=number,
        status=AccountStatus.BANNED, msg_count=msg_count
    )
