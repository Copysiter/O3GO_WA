from typing import Any, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

import app.crud as crud, app.models as models, app.schemas as schemas
from app import deps


router = APIRouter()


@router.get('/', response_model=List[schemas.OptionInt])
async def get_device_options(
    *,
    db: Session = Depends(deps.get_db),
    user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Retrieve android_device options.
    """
    f = {'user_id': user.id} if not user.is_superuser else None
    rows = await crud.android.get_rows(db, filter=f, limit=None)
    return JSONResponse([{
        'text': rows[i].device_name or rows[i].device,
        'value': rows[i].device
    } for i in range(len(rows))])
