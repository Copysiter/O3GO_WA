"""
Маршруты API для работы с сообщениями.

Функциональность
----------------
- Получение списка сообщений с фильтрацией, сортировкой и пагинацией
  (через fastapi-filter). Если параметр сортировки `order_by` не передан,
  применяется значение по умолчанию: `-id` (по убыванию).
- Создание, чтение, обновление и удаление сообщение.

Безопасность
------------
Все эндпоинты требуют авторизованного активного пользователя
(`deps.get_current_active_user`).

Зависимости
-----------
- SQLAlchemy AsyncSession (`deps.get_db`)
- fastapi-filter (`FilterDepends(schemas.MessageFilter)`)

Примеры сортировки
------------------
- По одному полю (ASC):   `GET /messages?order_by=id`
- По одному полю (DESC):  `GET /messages?order_by=-created_at`
- По двум полям:          `GET /messages?order_by=status&order_by=-id`

Примеры фильтров
----------------
По текстовому полю `number`:
- Равенство (eq):         `GET /messages?number__eq=12345`
- Вхождение (in):         `GET /messages?number__in=100,200,300`
- Подстрока (like/ilike): `GET /messages?number__like=%123%`
                          `GET /messages?number__ilike=%123%`
  Примечание: для `ilike` в фильтре должен быть определён атрибут
  `number__ilike: str | None = None`. В значении используются SQL-шаблоны
  (`%` — любой набор символов, `_` — один символ).

Другие примеры:
- По пользователю:        `GET /messages?user_id__eq=42`
- По статусам:            `GET /messages?status__in=1,2`
- По дате создания:       `GET /messages?created_at__gte=2025-09-01T00:00:00Z`
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


@router.get('/', response_model=schemas.MessageList)
async def read_messages(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.MessageFilter = FilterDepends(schemas.MessageFilter),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает список сообщений с поддержкой фильтрации,
    сортировки и пагинации.

    Если параметр сортировки `order_by` не указан, применяется сортировка
    по умолчанию: `-id` (DESC).

    Args:
        db: Асинхронная сессия базы данных.
        f: Фильтр `MessageFilter` (query-параметров через fastapi-filter).
        skip: Смещение (offset) для пагинации.
        limit: Максимальное число записей (limit) для пагинации.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.MessageList` вида:
        `{"data": [schemas.Message, ...], "total": <int>}` —
        где `total` учитывает применённый фильтр.

    Примеры:
        - `GET /messages?status__in=1,2&order_by=-id`
        - `GET /messages?user_id__eq=42&order_by=created_at&order_by=-id`
    """
    if not getattr(f, "order_by", None):
        f.order_by = ["-id"]
    data = await crud.message.list(db, filter=f, skip=skip, limit=limit)
    count = await crud.message.count(db, filter=f)
    return {'data': data, 'total': count}


@router.post(
    '/',
    response_model=schemas.Message,
    status_code=status.HTTP_201_CREATED
)
async def create_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.MessageCreate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Создаёт новое сообщение.

    Перед созданием выполняется проверка на уникальность по полю `number`.
    При обнаружении дубликата возвращается HTTP 400.

    Args:
        db: Асинхронная сессия базы данных.
        obj_in: Данные для создания сообщения (`schemas.MessageCreate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Созданный объект `schemas.Message` (HTTP 201).
    """
    db_obj = await crud.message.get_by(db, number=obj_in.number)
    if db_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='The message with this number already exists'
        )
    db_obj = await crud.message.create(db=db, obj_in=obj_in)
    return db_obj


@router.put('/{id}', response_model=schemas.Message)
async def update_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    obj_in: schemas.MessageUpdate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Обновляет данные сообщения по идентификатору.

    Возвращает 404, если сообщение не найден.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор сообщения.
        obj_in: Данные для обновления (`schemas.MessageUpdate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Обновлённый объект `schemas.Message`.
    """
    db_obj = await crud.message.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The message with this ID does not exist'
        )
    db_obj = await crud.message.update(db=db, db_obj=obj_in, obj_in=obj_in)
    return db_obj


@router.get('/{id}', response_model=schemas.Message)
async def read_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает сообщение по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор сообщения.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.Message`.

    Raises:
        HTTPException(404): Если сообщение не найдено.
    """
    db_obj = await crud.message.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The message with this ID does not exist'
        )
    return db_obj


@router.delete('/{id}', response_model=schemas.Message)
async def delete_message(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Удаляет сообщение по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор сообщения.
        _current_user: Текущий активный пользователь.

    Returns:
        Удалённый объект `schemas.Message`.

    Raises:
        HTTPException(404): Если сообщение не найдено.
    """
    db_obj = await crud.message.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The message with this ID does not exist'
        )
    db_obj = await crud.message.delete(db=db, id=id)
    return db_obj
