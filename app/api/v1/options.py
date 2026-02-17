from typing import Any, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

from app.core.logger import logger, E

import app.crud as crud, app.models as models, app.schemas as schemas
from app import deps


router = APIRouter()


@router.get('/', response_model=List[schemas.OptionInt])
async def get_device_options(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve android_device options.
    """
    try:
        f = {'user_id': current_user.id} \
            if not current_user.is_superuser else None
        rows = await crud.android.all(db, filter=f)
        return JSONResponse([{
            'text': rows[i].device_name or rows[i].device,
            'value': rows[i].device
        } for i in range(len(rows))])
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.get('/user', response_model=List[schemas.OptionInt])
async def get_user_options(
    *,
    db: Session = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve user options.
    """
    try:
        f = {'user_id': current_user.id} \
            if not current_user.is_superuser else None
        rows = await crud.user.all(db, filter=f)
        return JSONResponse([{
            'text': rows[i].name or rows[i].login,
            'value': rows[i].id
        } for i in range(len(rows))])
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
