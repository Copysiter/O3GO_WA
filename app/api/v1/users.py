"""
Маршруты API для работы с пользователями.

Функциональность
----------------
- Список пользователей с фильтрацией, сортировкой и пагинацией
  (через fastapi-filter). Если параметр сортировки `order_by` не передан,
  применяется значение по умолчанию: `-id` (по убыванию).
- Получение пользователя по id, текущего пользователя (`/me`).
- Создание, обновление и удаление пользователя.

Безопасность
------------
Большинство эндпоинтов требуют авторизованного пользователя.
Создание/чтение списка/удаление доступны только суперпользователю
(`deps.get_current_active_superuser`).

Зависимости
-----------
- SQLAlchemy AsyncSession (`deps.get_db`)
- fastapi-filter (`FilterDepends(schemas.UserFilter)`)

Примеры сортировки
------------------
- По одному полю (ASC):     `GET /users?order_by=id`
- По одному полю (DESC):    `GET /users?order_by=-created_at`
- По двум полям:            `GET /users?order_by=login&order_by=-id`

Примеры фильтров
----------------
По строковому полю `login`:
- Равенство (eq):           `GET /users?login=alex`
- Вхождение (in):           `GET /users?login__in=alex,ivan,petr`
- Подстрока (like/ilike):   `GET /users?login__like=%al%`
                            `GET /users?login__ilike=%al%`(регистр-независимо)

По числовому полю `id`:
- Равенство:               `GET /users?id=100`
- Вхождение:               `GET /users?id__in=1,2,3`

По датам:
- По дате создания: `GET /users?created_at__gte=2025-09-01T00:00:00Z`
"""

from typing import Any, Annotated

from fastapi import APIRouter, Body, Depends, Query, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas


router = APIRouter()


@router.get('/', response_model=schemas.UserList)
async def read_users(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.UserFilter = FilterDepends(schemas.UserFilter),
    skip: Annotated[int, Query(description='Page offset', ge=0)] = 0,
    limit: Annotated[int, Query(description='Page size', ge=1)] = 100,
    _current_user: models.User = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Возвращает список пользователей с поддержкой фильтрации,
    сортировки и пагинации.

    Если параметр сортировки `order_by` не указан, применяется
    сортировка по умолчанию: `-id` (DESC).

    Args:
        db: Асинхронная сессия SQLAlchemy.
        f: Фильтр `UserFilter` (из query-параметров через fastapi-filter).
        skip: Смещение (offset) для пагинации.
        limit: Максимальное число записей (limit) для пагинации.
        _current_user: Текущий активный суперпользователь.

    Returns:
        Объект `schemas.UserList` вида:
        `{"data": [schemas.User, ...], "total": <int>}` —
        где `total` учитывает применённый фильтр.

    Примеры:
        - `GET /users?login__ilike=%al%&order_by=login&order_by=-id`
        - `GET /users?id__in=1,2,3&order_by=-id`
    """
    try:
        if not getattr(f, "order_by", None):
            f.order_by = ["-id"]
        data = await crud.user.list(db, filter=f, skip=skip, limit=limit)
        count = await crud.user.count(db, filter=f)
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
    response_model=schemas.User,
    status_code=status.HTTP_201_CREATED
)
async def create_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.UserCreate,
    _current_user: models.User = Depends(deps.get_current_active_superuser)
) -> Any:
    """
    Создаёт нового пользователя.

    Перед созданием выполняется проверка на уникальность по полю `login`.
    При обнаружении дубликата возвращается HTTP 400.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        obj_in: Данные для создания пользователя (`schemas.UserCreate`).
        _current_user: Текущий активный суперпользователь.

    Returns:
        Созданный объект `schemas.User` (HTTP 201).
    """
    try:
        user = await crud.user.get_by(db, login=obj_in.login)
        if user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='The user with this ID already exists',
            )
        user = await crud.user.create(db, obj_in=obj_in)
        return user
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.put('/me', response_model=schemas.User)
async def update_current_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    password: str = Body(None),
    name: str = Body(None),
    login: str = Body(None),
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Обновляет данные текущего пользователя.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        password: Новый пароль (опционально).
        name: Новое имя (опционально).
        login: Новый логин (опционально).
        current_user: Текущий активный пользователь.

    Returns:
        Обновлённый объект `schemas.User`.
    """
    try:
        current_user_data = jsonable_encoder(current_user)
        user_in = schemas.UserUpdate(**current_user_data)
        if password is not None:
            user_in.password = password
        if name is not None:
            user_in.name = name
        if login is not None:
            user_in.login = login
        user = await crud.user.update(db, db_obj=current_user, obj_in=user_in)
        return user
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.get('/me', response_model=schemas.User)
async def read_curent_user(
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Возвращает данные текущего пользователя.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.User`.
    """
    try:
        return current_user
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.get('/{id}', response_model=schemas.User)
async def read_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    current_user: models.User = Depends(deps.get_current_active_user)
) -> Any:
    """
    Возвращает пользователя по идентификатору.

    Если запрашивается не текущий пользователь и текущий пользователь
    не является суперпользователем — будет возвращена ошибка 400.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Идентификатор пользователя.
        current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.User`.

    Raises:
        HTTPException(404): Если пользователь не найден.
        HTTPException(400): Недостаточно прав для просмотра чужого профиля.
    """
    try:
        user = await crud.user.get(db, id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The user with this ID does not exist'
            )
        if user == current_user:
            return user
        if not crud.user.is_superuser(current_user):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The user doesn't have enough privileges",
            )
        return user
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.put('/{id}', response_model=schemas.User)
async def update_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    obj_in: schemas.UserUpdate,
    _current_user: models.User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Обновляет пользователя по идентификатору.

    Доступно только суперпользователю.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Идентификатор пользователя.
        obj_in: Данные для обновления (`schemas.UserUpdate`).
        _current_user: Текущий активный суперпользователь.

    Returns:
        Обновлённый объект `schemas.User`.

    Raises:
        HTTPException(404): Если пользователь не найден.
    """
    try:
        user = await crud.user.get(db, id=id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The user with this ID does not exist',
            )
        user = await crud.user.update(db, db_obj=user, obj_in=obj_in)
        return user
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.delete('/{id}', response_model=schemas.User)
async def delete_user(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_superuser),
) -> Any:
    """
    Удаляет пользователя по идентификатору.

    Доступно только суперпользователю.

    Args:
        db: Асинхронная сессия SQLAlchemy.
        id: Идентификатор пользователя.
        _current_user: Текущий активный суперпользователь.

    Returns:
        Удалённый объект `schemas.User`.

    Raises:
        HTTPException(404): Если пользователь не найден.
    """
    try:
        user = await crud.user.get(db=db, id=id)
        if not user:
            raise HTTPException(
                status_code=404,
                detail='The user with this ID does not exist'
            )
        user = await crud.user.delete(db=db, id=id)
        return user
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
