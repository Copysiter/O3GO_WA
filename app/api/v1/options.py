from typing import Any, List

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

import app.crud as crud, app.models as models, app.schemas as schemas  # noqa
from api import deps  # noqa


router = APIRouter()


@router.get('/user', response_model=List[schemas.OptionInt])
async def get_user_options(
    *,
    db: Session = Depends(deps.get_db),
    user: models.User = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Retrieve user options.
    """
    f = [{'user_id', user.id}] if not user.is_superuser else []
    data = await crud.user.list(db, filter=f, limit=None)
    return JSONResponse([{
        'text': data[i].name if data[i].name else data[i].login,
        'value': data[i].id
    } for i in range(len(data))])