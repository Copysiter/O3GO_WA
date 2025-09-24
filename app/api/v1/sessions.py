"""
Маршруты API для работы с сессиями аккаунтов.

Функциональность
----------------
- Получение списка сессий аккаунтов с фильтрацией, сортировкой и пагинацией
  (через fastapi-filter). Если параметр сортировки `order_by` не передан,
  применяется значение по умолчанию: `-id` (по убыванию).
- Создание, чтение, обновление и удаление сессий аккаунтов.

Безопасность
------------
Все эндпоинты требуют авторизованного активного пользователя
(`deps.get_current_active_user`).

Зависимости
-----------
- SQLAlchemy AsyncSession (`deps.get_db`)
- fastapi-filter (`FilterDepends(schemas.SessionFilter)`)

Примеры сортировки
------------------
- По одному полю (ASC):   `GET /sessions?order_by=id`
- По одному полю (DESC):  `GET /sessions?order_by=-created_at`
- По двум полям:          `GET /sessions?order_by=status&order_by=-id`

Примеры фильтров
----------------
По текстовому полю `ext_id`:
- Равенство (eq):         `GET /sessions?ext_id__eq=12345`
- Вхождение (in):         `GET /sessions?ext_id__in=100,200,300`
- Подстрока (like/ilike): `GET /sessions?ext_id__like=%123%`
                          `GET /sessions?ext_id__ilike=%123%`
  Примечание: для `ilike` в фильтре должен быть определён атрибут
  `ext_id__ilike: str | None = None`. В значении используются SQL-шаблоны
  (`%` — любой набор символов, `_` — один символ).

Другие примеры:
- По аккаунту:        `GET /sessions?account__eq=42`
- По статусам:            `GET /sessions?status__in=1,2`
- По дате создания:       `GET /sessions?created_at__gte=2025-09-01T00:00:00Z`
"""

from typing import Any

from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi_filter import FilterDepends
from sqlalchemy.ext.asyncio import AsyncSession

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas


router = APIRouter()


@router.get('/', response_model=schemas.SessionList)
async def read_sessions(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.SessionFilter = FilterDepends(schemas.SessionFilter),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает список сессий аккаунтов с поддержкой фильтрации,
    сортировки и пагинации.

    Если параметр сортировки `order_by` не указан, применяется сортировка
    по умолчанию: `-id` (DESC).

    Args:
        db: Асинхронная сессия базы данных.
        f: Фильтр `SessionFilter` (query-параметров через fastapi-filter).
        skip: Смещение (offset) для пагинации.
        limit: Максимальное число записей (limit) для пагинации.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.SessionList` вида:
        `{"data": [schemas.Session, ...], "total": <int>}` —
        где `total` учитывает применённый фильтр.

    Примеры:
        - `GET /sessions?status__in=1,2&order_by=-id`
        - `GET /sessions?account_id__eq=42&order_by=created_at&order_by=-id`
    """
    if not getattr(f, "order_by", None):
        f.order_by = ["-id"]
    data = await crud.session.list(db, filter=f, skip=skip, limit=limit)
    count = await crud.session.count(db, filter=f)
    return {'data': data, 'total': count}


@router.post(
    '/',
    response_model=schemas.Session,
    status_code=status.HTTP_201_CREATED
)
async def create_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.SessionCreate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Создаёт новую сессию аккаунта.

    Перед созданием выполняется проверка на уникальность по полю `ext_id`.
    При обнаружении дубликата возвращается HTTP 400.

    Args:
        db: Асинхронная сессия базы данных.
        obj_in: Данные для создания аккаунта (`schemas.SessionCreate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Созданный объект `schemas.Session` (HTTP 201).
    """
    db_obj = await crud.session.get_by(db, number=obj_in.number)
    if db_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='The session with this number already exists'
        )
    db_obj = await crud.session.create(db=db, obj_in=obj_in)
    return db_obj


@router.put('/{id}', response_model=schemas.Session)
async def update_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    obj_in: schemas.SessionUpdate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Обновляет данные сессии аккаунта по идентификатору.

    Возвращает 404, если аккаунт не найден.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        obj_in: Данные для обновления (`schemas.SessionUpdate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Обновлённый объект `schemas.Session`.
    """
    db_obj = await crud.session.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The session with this ID does not exist'
        )
    db_obj = await crud.session.update(db=db, db_obj=obj_in, obj_in=obj_in)
    return db_obj


@router.get('/{id}', response_model=schemas.Session)
async def read_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает сессию аккаунта по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.Session`.

    Raises:
        HTTPException(404): Если сессия аккаунта не найдена.
    """
    db_obj = await crud.session.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The session with this ID does not exist'
        )
    return db_obj


@router.delete('/{id}', response_model=schemas.Session)
async def delete_session(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Удаляет аккаунт по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор сессии аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Удалённый объект `schemas.Session`.

    Raises:
        HTTPException(404): Если сессия аккаунта не найдена.
    """
    db_obj = await crud.session.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The session with this ID does not exist'
        )
    db_obj = await crud.session.delete(db=db, id=id)
    return db_obj
