from typing import Any

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud, app.models as models, app.schemas as schemas
from app.schemas.enum import AccountStatus

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
    number: str = Query(..., max_length=64, description="Номер аккаунта/получателя"),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Стартует сессию: проверяет, нет ли в БД с таким ext_id, и создаёт новую."""
    account = await crud.account.get_by(db, number=number)
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account with number={number} not found",
        )

    existing = await crud.session.get_by(db, ext_id=id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Session with ext_id={id} already exists",
        )

    obj_in = schemas.SessionCreate(
        account_id=account.id, ext_id=id, status=AccountStatus.ACTIVE
    )
    new_session = await crud.session.create(db=db, obj_in=obj_in)

    return schemas.SessionStatusResponse(
        id=new_session.ext_id, number=account.number, status=new_session.status
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
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как завершённую (статус AVAILABLE)."""
    db_obj = await crud.session.get_by(db, ext_id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ext_id={id} not found",
        )

    account = await crud.account.get(db, db_obj.account_id)
    if not account or account.number != number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account mismatch for provided session id and number",
        )

    updated = await crud.session.update(
        db, db_obj=db_obj, obj_in={"status": AccountStatus.AVAILABLE}
    )
    return schemas.SessionStatusResponse(
        id=updated.ext_id, number=account.number, status=updated.status
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
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как заблокированную (статус BANNED)."""
    db_obj = await crud.session.get_by(db, ext_id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ext_id={id} not found",
        )

    account = await crud.account.get(db, db_obj.account_id)
    if not account or account.number != number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account mismatch for provided session id and number",
        )

    updated = await crud.session.update(
        db, db_obj=db_obj, obj_in={"status": AccountStatus.BANNED}
    )
    return schemas.SessionStatusResponse(
        id=updated.ext_id, number=account.number, status=updated.status
    )
