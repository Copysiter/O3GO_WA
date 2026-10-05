import asyncio

from fastapi import (
    APIRouter, Query, Depends, HTTPException, status as http_status
)
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas
from app.services.log import log_service
from app.services.session_error import SessionErrorAudit
from app.models.session import AccountStatus, SessionStatus


router = APIRouter()


async def _update_session_status(
    db: AsyncSession,
    id: int | None = None,
    ext_id: str | None = None,
    *,
    user_id: int,
    number: str,
    info_1: str | None = None,
    info_2: str | None = None,
    info_3: str | None = None,
    info_4: str | None = None,
    info_5: str | None = None,
    info_6: str | None = None,
    info_7: str | None = None,
    info_8: str | None = None,
    status: AccountStatus,
    audit: SessionErrorAudit | None = None,
) -> schemas.SessionStatusResponse:
    """Обновляет статус сессии, проверяя связанный аккаунт."""
    audit = audit or SessionErrorAudit(
        action="session.ban" if status == AccountStatus.BANNED
        else "session.finish",
        user_id=user_id,
    )
    audit.stage = "lookup_session"
    if id:
        session = await crud.session.get(db, id)
    elif ext_id:
        session = await crud.session.get_by(db, ext_id=ext_id)
    else:
        audit.stage = "validate"
        audit.error_code = "missing_session_reference"
        raise HTTPException(
            status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Missing required field: 'session_id' or 'session_ext_id'."
        )
    if not session or session.account.user_id != user_id:
        audit.error_code = "session_not_found"
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Session '{ext_id}' not found",
        )

    audit.account_id = session.account_id
    audit.session_id = session.id
    audit.stage = "lookup_account"
    account = await crud.account.get(db, session.account_id)
    if not account or account.number != number:
        audit.error_code = "account_mismatch"
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Account mismatch for provided session id and number",
        )

    # Обновляем сессию - всегда с переданным статусом
    audit.stage = "update_session"
    session_obj_in = schemas.SessionUpdate(status=status)
    for info in [
        'info_1', 'info_2', 'info_3',
        'info_4', 'info_5', 'info_6',
        'info_7', 'info_8'
    ]:
        if locals()[info] is not None:
            setattr(session_obj_in, info, locals()[info])

    session = await crud.session.update(
        db, db_obj=session, obj_in=session_obj_in, commit=False
    )

    # Для аккаунта применяем логику с attempts при бане
    audit.stage = "update_account"
    if status == AccountStatus.BANNED:
        if account.attempts > 1:
            account_status = AccountStatus.AVAILABLE
            account_attempts = account.attempts - 1
        else:
            account_status = AccountStatus.BANNED
            account_attempts = 0

        account_obj_in = schemas.AccountUpdate(
            status=account_status, attempts=account_attempts
        )
    else:
        account_obj_in = schemas.AccountUpdate(status=status)

    # Копируем info поля в account_obj_in
    for info in [
        'info_1', 'info_2', 'info_3',
        'info_4', 'info_5', 'info_6',
        'info_7', 'info_8'
    ]:
        if locals()[info] is not None:
            setattr(account_obj_in, info, locals()[info])

    account = await crud.account.update(
        db, db_obj=account, obj_in=account_obj_in, commit=False
    )

    audit.stage = "audit"
    await log_service.records(
        db,
        items=[
            schemas.LogCreate(
                event="session.status",
                source="ext_api",
                account_id=account.id,
                session_id=session.id,
                user_id=user_id,
                status=session.status
            ),
            schemas.LogCreate(
                event="account.status",
                source="ext_api",
                account_id=account.id,
                session_id=session.id,
                user_id=user_id,
                status=account.status
            )
        ],
        commit=False
    )

    audit.stage = "commit"
    audit.db_outcome = "unknown"
    await db.commit()
    audit.db_outcome = "committed"

    audit.stage = "prepare_response"
    return schemas.SessionStatusResponse(
        id=session.id,
        ext_id=session.ext_id,
        number=account.number,
        status=SessionStatus(session.status).name.lower(),
        msg_count=session.msg_count
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
        ..., max_length=64, description="Номер аккаунта"
    ),
    device: str | None = Query(
        None,
        alias="api_key",
        description=(
            "Идентификатор устройства; не используется для аутентификации"
        )
    ),
    info_1: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 1"
    ),
    info_2: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 2"
    ),
    info_3: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 3"
    ),
    info_4: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 4"
    ),
    info_5: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 5"
    ),
    info_6: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 6"
    ),
    info_7: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 7"
    ),
    info_8: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 8"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """
    Стартует сессию:
    если аккаунта нет — создаёт, если сессия уже существует — ошибка.

    Query-параметр `api_key` сохраняется как device сессии и не заменяет
    аутентификацию через `X-Api-Key` или `x_api_key`.
    """
    audit = SessionErrorAudit(action="session.start", user_id=user.id)
    try:
        # Проверяем, нет ли уже сессии с таким ext_id
        audit.stage = "lookup_session"
        existing = await crud.session.get_by(db, ext_id=ext_id)
        if existing:
            audit.error_code = "session_exists"
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Session with ext_id={ext_id} already exists",
            )

        # Проверяем аккаунт, если нет — создаём
        audit.stage = "lookup_account"
        account = await crud.account.get_by(
            db, number=number, user_id=user.id
        )
        if account:
            audit.account_id = account.id
            audit.stage = "update_account"
            account_event = "account.status"
            # Формируем obj_in только с не-None значениями
            obj_in = schemas.AccountUpdate(status=AccountStatus.ACTIVE)
            for info in [
                'info_1', 'info_2', 'info_3',
                'info_4', 'info_5', 'info_6',
                'info_7', 'info_8'
            ]:
                if locals()[info] is not None:
                    setattr(obj_in, info, locals()[info])

            account = await crud.account.update(
                db, db_obj=account, obj_in=obj_in, commit=False
            )

            audit.stage = "close_sessions"
            closed_sessions = await crud.session.update(
                db,
                obj_in=schemas.SessionUpdate(status=SessionStatus.FINISHED),
                filter={
                    "account_id": account.id,
                    "status__in": [SessionStatus.ACTIVE, SessionStatus.PAUSED]
                },
                commit=False
            )
        else:
            audit.stage = "create_account"
            account_event = "account.create"
            # Формируем obj_in_create только с не-None значениями
            obj_in = schemas.AccountCreate(
                number=number,
                user_id=user.id,
                status=AccountStatus.ACTIVE
            )
            for info in [
                'info_1', 'info_2', 'info_3',
                'info_4', 'info_5', 'info_6',
                'info_7', 'info_8'
            ]:
                if locals()[info] is not None:
                    setattr(obj_in, info, locals()[info])

            account = await crud.account.create(
                db=db, obj_in=obj_in, commit=False,
            )
            audit.new_account_id = account.id
            closed_sessions = []

        # Создаём новую сессию
        audit.stage = "create_session"
        obj_in = schemas.SessionCreate(
            account_id=account.id,
            ext_id=ext_id,
            device=device,
            status=AccountStatus.ACTIVE
        )
        for info in [
            'info_1', 'info_2', 'info_3',
            'info_4', 'info_5', 'info_6',
            'info_7', 'info_8'
        ]:
            if locals()[info] is not None:
                setattr(obj_in, info, locals()[info])

        session = await crud.session.create(
            db=db, obj_in=obj_in, commit=False,
        )
        audit.new_session_id = session.id

        audit.stage = "audit"
        log_items = [
            schemas.LogCreate(
                event=account_event,
                source="ext_api",
                account_id=account.id,
                session_id=session.id,
                user_id=user.id,
                status=account.status
            ),
            schemas.LogCreate(
                event="session.create",
                source="ext_api",
                account_id=account.id,
                session_id=session.id,
                user_id=user.id,
                status=session.status
            )
        ]
        log_items.extend(
            schemas.LogCreate(
                event="session.status",
                source="ext_api",
                account_id=closed_session.account_id,
                session_id=closed_session.id,
                user_id=user.id,
                status=closed_session.status
            )
            for closed_session in closed_sessions
        )
        await log_service.records(db, items=log_items, commit=False)

        audit.stage = "commit"
        audit.db_outcome = "unknown"
        await db.commit()
        audit.db_outcome = "committed"

        audit.stage = "prepare_response"
        return schemas.SessionStatusResponse(
            id=session.id,
            ext_id=session.ext_id,
            number=account.number,
            status=SessionStatus(session.status).name.lower(),
            msg_count=session.msg_count
        )
    except (Exception, asyncio.CancelledError) as error:
        await audit.report(db, error)
        raise


@router.get(
    "/finish",
    response_model=schemas.SessionStatusResponse,
    status_code=http_status.HTTP_200_OK
)
async def finish_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int | None = Query(None, description="ID сессии аккаунта"),
    ext_id: str | None = Query(
        None, description="Внешний ID сессии аккаунта"
    ),
    number: str = Query(..., max_length=64, description="Номер аккаунта"),
    info_1: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 1"
    ),
    info_2: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 2"
    ),
    info_3: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 3"
    ),
    info_4: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 4"
    ),
    info_5: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 5"
    ),
    info_6: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 6"
    ),
    info_7: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 7"
    ),
    info_8: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 8"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как завершённую (AVAILABLE)."""
    audit = SessionErrorAudit(action="session.finish", user_id=user.id)
    try:
        return await _update_session_status(
            db, id=id,
            ext_id=ext_id,
            user_id=user.id,
            number=number,
            audit=audit,
            status=AccountStatus.AVAILABLE,
            info_1=info_1,
            info_2=info_2,
            info_3=info_3,
            info_4=info_4,
            info_5=info_5,
            info_6=info_6,
            info_7=info_7,
            info_8=info_8
        )
    except (Exception, asyncio.CancelledError) as error:
        await audit.report(db, error)
        raise


@router.get(
    "/ban",
    response_model=schemas.SessionStatusResponse,
    status_code=http_status.HTTP_200_OK,
)
async def ban_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int | None = Query(None, description="ID сессии аккаунта"),
    ext_id: str | None = Query(
        None, description="Внешний ID сессии аккаунта"
    ),
    number: str = Query(..., max_length=64, description="Номер аккаунта"),
    info_1: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 1"
    ),
    info_2: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 2"
    ),
    info_3: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 3"
    ),
    info_4: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 4"
    ),
    info_5: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 5"
    ),
    info_6: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 6"
    ),
    info_7: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 7"
    ),
    info_8: str | None = Query(
        None, max_length=256, description="Служебное инфо поле 8"
    ),
    user: models.User = Depends(deps.get_user_by_api_key),
) -> schemas.SessionStatusResponse:
    """Помечает сессию как заблокированную (BANNED) и обновляет."""
    audit = SessionErrorAudit(action="session.ban", user_id=user.id)
    try:
        return await _update_session_status(
            db, id=id,
            ext_id=ext_id,
            user_id=user.id,
            number=number,
            audit=audit,
            status=AccountStatus.BANNED,
            info_1=info_1,
            info_2=info_2,
            info_3=info_3,
            info_4=info_4,
            info_5=info_5,
            info_6=info_6,
            info_7=info_7,
            info_8=info_8
        )
    except (Exception, asyncio.CancelledError) as error:
        await audit.report(db, error)
        raise
