"""Маршруты API для работы с логами событий."""

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E
from app.crud.filter.base import FilterDepends

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas


router = APIRouter()


@router.get('/', response_model=schemas.LogList)
async def read_logs(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.LogFilter = FilterDepends(schemas.LogFilter),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """Возвращает список событий с фильтрацией и пагинацией."""
    try:
        if not getattr(f, "order_by", None):
            f.order_by = ["-id"]
        if not current_user.is_superuser:
            f.user_id = current_user.id
        data = await crud.log.list(db, filter=f, skip=skip, limit=limit)
        count = await crud.log.count(db, filter=f)
        return {'data': data, 'total': count}
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
