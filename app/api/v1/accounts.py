"""
Маршруты API для работы с аккаунтами.

Функциональность
----------------
- Получение списка аккаунтов с фильтрацией, сортировкой и пагинацией
  (через fastapi-filter). Если параметр сортировки `order_by` не передан,
  применяется значение по умолчанию: `-id` (по убыванию).
- Создание, чтение, обновление и удаление аккаунта.

Безопасность
------------
Все эндпоинты требуют авторизованного активного пользователя
(`deps.get_current_active_user`).

Зависимости
-----------
- SQLAlchemy AsyncSession (`deps.get_db`)
- fastapi-filter (`FilterDepends(schemas.AccountFilter)`)

Примеры сортировки
------------------
- По одному полю (ASC):   `GET /accounts?order_by=id`
- По одному полю (DESC):  `GET /accounts?order_by=-created_at`
- По двум полям:          `GET /accounts?order_by=status&order_by=-id`

Примеры фильтров
----------------
По текстовому полю `number`:
- Равенство (eq):         `GET /accounts?number__eq=12345`
- Вхождение (in):         `GET /accounts?number__in=100,200,300`
- Подстрока (like/ilike): `GET /accounts?number__like=%123%`
                          `GET /accounts?number__ilike=%123%`
  Примечание: для `ilike` в фильтре должен быть определён атрибут
  `number__ilike: str | None = None`. В значении используются SQL-шаблоны
  (`%` — любой набор символов, `_` — один символ).

Другие примеры:
- По пользователю:        `GET /accounts?user_id__eq=42`
- По статусам:            `GET /accounts?status__in=1,2`
- По дате создания:       `GET /accounts?created_at__gte=2025-09-01T00:00:00Z`
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


@router.get('/', response_model=schemas.AccountList)
async def read_accounts(
    db: AsyncSession = Depends(deps.get_db),
    f: schemas.AccountFilter = FilterDepends(schemas.AccountFilter),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает список аккаунтов с поддержкой фильтрации,
    сортировки и пагинации.

    Если параметр сортировки `order_by` не указан, применяется сортировка
    по умолчанию: `-id` (DESC).

    Args:
        db: Асинхронная сессия базы данных.
        f: Фильтр `AccountFilter` (query-параметров через fastapi-filter).
        skip: Смещение (offset) для пагинации.
        limit: Максимальное число записей (limit) для пагинации.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.AccountList` вида:
        `{"data": [schemas.Account, ...], "total": <int>}` —
        где `total` учитывает применённый фильтр.

    Примеры:
        - `GET /accounts?status__in=1,2&order_by=-id`
        - `GET /accounts?user_id__eq=42&order_by=created_at&order_by=-id`
    """
    if not getattr(f, "order_by", None):
        f.order_by = ["-id"]
    data = await crud.account.list(db, filter=f, skip=skip, limit=limit)
    count = await crud.account.count(db, filter=f)
    return {'data': data, 'total': count}


@router.post(
    '/',
    response_model=schemas.Account,
    status_code=status.HTTP_201_CREATED
)
async def create_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AccountCreate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Создаёт новый аккаунт.

    Перед созданием выполняется проверка на уникальность по полю `number`.
    При обнаружении дубликата возвращается HTTP 400.

    Args:
        db: Асинхронная сессия базы данных.
        obj_in: Данные для создания аккаунта (`schemas.AccountCreate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Созданный объект `schemas.Account` (HTTP 201).
    """
    db_obj = await crud.account.get_by(db, number=obj_in.number)
    if db_obj:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='The account with this number already exists'
        )
    db_obj = await crud.account.create(db=db, obj_in=obj_in)
    return db_obj


@router.put('/{id}', response_model=schemas.Account)
async def update_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    obj_in: schemas.AccountUpdate,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Обновляет данные аккаунта по идентификатору.

    Возвращает 404, если аккаунт не найден.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        obj_in: Данные для обновления (`schemas.AccountUpdate`).
        _current_user: Текущий активный пользователь.

    Returns:
        Обновлённый объект `schemas.Account`.
    """
    db_obj = await crud.account.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The account with this ID does not exist'
        )
    db_obj = await crud.account.update(db=db, db_obj=obj_in, obj_in=obj_in)
    return db_obj


@router.get('/{id}', response_model=schemas.Account)
async def read_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Возвращает аккаунт по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Объект `schemas.Account`.

    Raises:
        HTTPException(404): Если аккаунт не найден.
    """
    db_obj = await crud.account.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The account with this ID does not exist'
        )
    return db_obj


@router.delete('/{id}', response_model=schemas.Account)
async def delete_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    id: int,
    _current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Удаляет аккаунт по идентификатору.

    Args:
        db: Асинхронная сессия базы данных.
        id: Идентификатор аккаунта.
        _current_user: Текущий активный пользователь.

    Returns:
        Удалённый объект `schemas.Account`.

    Raises:
        HTTPException(404): Если аккаунт не найден.
    """
    db_obj = await crud.account.get(db=db, id=id)
    if not db_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='The account with this ID does not exist'
        )
    db_obj = await crud.account.delete(db=db, id=id)
    return db_obj
