from typing import Any, List  # noqa

from fastapi import APIRouter, Query, Depends, HTTPException, status  # noqa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E
from app.crud.filter import FilterDepends

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas


router = APIRouter()


@router.get('/', response_model=schemas.AndroidRows)
async def read_androids(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.AndroidFilter = FilterDepends(schemas.AndroidFilter),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает список Android устройств с поддержкой фильтрации,
    сортировки и пагинации.

    Если параметр сортировки `order_by` не указан, применяется сортировка
    по умолчанию: `-id` (DESC).

    Args:
        db: Асинхронная сессия базы данных.
        f: Фильтр `AndroidFilter` (query-параметров через fastapi-filter).
        skip: Смещение (offset) для пагинации.
        limit: Максимальное число записей (limit) для пагинации.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.AndroidList` вида:
        `{"data": [schemas.Android, ...], "total": <int>}` —
        где `total` учитывает применённый фильтр.

    Примеры:
        - `GET /androids?device=1,2&order_by=-id`
        - `GET /androids?user_id=42&order_by=device&order_by=-id`
    """
    try:
        if not getattr(f, "order_by", None):
            f.order_by = ["-id"]
        data = await crud.android.list(db, filter=f, skip=skip, limit=limit)
        count = await crud.android.count(db, filter=f)
        return {'data': data, 'total': count}
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post(
    '/',
    response_model=schemas.Android,
    status_code=status.HTTP_201_CREATED
)
async def add_android_device(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AndroidCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Добавляет новое Android устройство.

    Перед созданием выполняется проверка на уникальность по полю `device`.
    При обнаружении дубликата возвращается HTTP 400.

    Args:
        db: Асинхронная сессия базы данных.
        obj_in: Данные для создания аккаунта (`schemas.AndroidCreate`).
        current_user: Текущий активный пользователь.

    Returns:
        Созданный объект `schemas.Android` (HTTP 201).
    """
    try:
        db_obj = await crud.android.get_by(db, device=obj_in.device)
        if db_obj:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='This device already exists in the system.',
            )
        obj_in.user_id = current_user.id
        db_obj = await crud.android.create(db=db, obj_in=obj_in)
        return db_obj
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.put('/{id}', response_model=schemas.Android)
async def update_android_device(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    obj_in: schemas.AndroidUpdate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Обновляет данные Android девайса по идентификатору.

    Возвращает 404, если аккаунт не найден.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        obj_in: Данные для обновления (`schemas.AndroidUpdate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Обновлённый объект `schemas.Android`.
    """
    try:
        db_obj = await crud.android.get(db=db, id=id)
        if not db_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Device with this ID does not exist'
            )
        account = await crud.android.update(
            db=db, db_obj=db_obj, obj_in=obj_in
        )
        return account
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.get('/{id}', response_model=schemas.Android)
async def read_android_device(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает Android девайс по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.Android`.

    Raises:
        HTTPException(404): Если Android девайс не найден.
    """
    try:
        android = await crud.android.get(db=db, id=id)
        if not android:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Device with this ID does not exist'
            )
        return android
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.delete('/{id}', response_model=schemas.Android)
async def delete_android_device(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Удаляет Android девайс по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Удалённый объект `schemas.Android`.

    Raises:
        HTTPException(404): Если Android девайс не найден.
    """
    try:
        android = await crud.android.get(db=db, id=id)
        if not android:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Device with this ID does not exist'
            )
        android = await crud.android.delete(db=db, id=id)
        return android
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
