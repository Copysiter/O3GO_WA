from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

import app.crud as crud, app.models as models, app.schemas as schemas

from app import deps
from app.core.logger import logger, E


router = APIRouter()


@router.get('', response_model=List[schemas.OptionInt])
async def get_android_device_options(
    *,
    db: Session = Depends(deps.get_db),
    user: models.User = Depends(deps.get_user_by_api_key)
) -> Any:
    """
    Retrieve android_device options.
    """
    try:
        f = {'user_id': user.id} if not user.is_superuser else None
        rows = await crud.android.all(db, filter=f)
        return JSONResponse([{
            'text': rows[i].device_name or rows[i].device,
            'value': rows[i].device
        } for i in range(len(rows))])
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(
            f'Get android options error: {type(e).__name__}: {str(e)}',
            event=E.SYSTEM.API.ERROR,
            extra={
                'user_id': user.id,
                'error': {'type': type(e).__name__, 'msg': str(e)}
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'{type(e).__name__}: {str(e)}'
        )
