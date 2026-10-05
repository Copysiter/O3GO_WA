from typing import Any, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.logger import logger, E

import app.crud as crud
import app.models as models
import app.schemas as schemas
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
    db: AsyncSession = Depends(deps.get_db),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> list[dict[str, str | int]]:
    """Return safe owner options, including inactive owners for admins.

    Members can only select themselves, regardless of client parameters.
    """
    owner_id = None if current_user.is_superuser else current_user.id
    return await crud.user.get_options(db, owner_id=owner_id)
