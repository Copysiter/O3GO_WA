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
- Равенство (eq):         `GET /accounts?number=12345`
- Вхождение (in):         `GET /accounts?number__in=100,200,300`
- Подстрока (like/ilike): `GET /accounts?number__like=%123%`
                          `GET /accounts?number__ilike=%123%`
  Примечание: для `ilike` в фильтре должен быть определён атрибут
  `number__ilike: str | None = None`. В значении используются SQL-шаблоны
  (`%` — любой набор символов, `_` — один символ).

Другие примеры:
- По пользователю:        `GET /accounts?user_id=42`
- По статусам:            `GET /accounts?status__in=1,2`
- По дате создания:       `GET /accounts?created_at__gte=2025-09-01T00:00:00Z`
"""

import uuid, shutil  # noqa

from typing import Any
from pathlib import Path
from datetime import datetime, timedelta, timezone

from fastapi import (
    APIRouter, Query, Depends, Request,
    UploadFile, File, HTTPException, status
)

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logger import logger, E
from app.models.account import AccountStatus
from app.crud.filter import FilterDepends

import app.deps as deps
import app.crud as crud
import app.models as models
import app.schemas as schemas


UPLOAD_DIR = Path('upload/wa')
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

PROFILE_UPLOAD_DIR = Path('upload/wa/profile')
PROFILE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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
        - `GET /accounts?user_id=42&order_by=created_at&order_by=-id`
    """
    try:
        if not getattr(f, "order_by", None):
            f.order_by = ["-id"]
        data = await crud.account.list(db, filter=f, skip=skip, limit=limit)
        count = await crud.account.count(db, filter=f)

        now = datetime.now(timezone.utc)
        data = list(map(
            lambda item: (
                setattr(item, 'status', AccountStatus.PAUSED) or item
            ) if (
                item.cooldown is not None and item.updated_at is not None
                and now > item.updated_at + timedelta(minutes=item.cooldown)
            ) else item, data
        ))
        
        return {'data': data, 'total': count}
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post(
    '/', status_code=status.HTTP_201_CREATED
)
async def create_account(
    *,
    db: AsyncSession = Depends(deps.get_db),
    obj_in: schemas.AccountMultiCreate,
    current_user: models.User = Depends(deps.get_current_active_user),
) -> Any:
    """
    Создаёт новый аккаунт.

    Перед созданием выполняется проверка на уникальность по полю `number`.
    При обнаружении дубликата возвращается HTTP 400.

    Args:
        db: Асинхронная сессия базы данных.
        obj_in: Данные для создания аккаунта (`schemas.AccountCreate`).
        current_user: Текущий активный пользователь.

    Returns:
        Созданный объект `schemas.Account` (HTTP 201).
    """
    try:
        base_data = {
            **obj_in.model_dump(
                exclude={
                    "files", "uuid", "user_id", "file_name", "session_count"
                }
            ),
            "user_id": current_user.id,
        }
        obj_list = [
            schemas.AccountCreate(
                **base_data, uuid=str(uuid.uuid4()), file_name=file_name
            )
            for file_name in obj_in.files
        ]
        accounts = await crud.account.insert(
            db=db, obj_list=obj_list, returning=True
        )
        return {"count": len(accounts)}
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


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
    try:
        db_obj = await crud.account.get(db=db, id=id)
        if not db_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )
        account = await crud.account.update(db=db, db_obj=db_obj, obj_in=obj_in)
        return account
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


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
    try:
        account = await crud.account.get(db=db, id=id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )
        return account
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


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
    try:
        account = await crud.account.get(db=db, id=id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='The account with this ID does not exist'
            )
        account = await crud.account.delete(db=db, id=id)
        return account
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post('/upload')
async def upload_archive(file: UploadFile = File(...)):
    try:
        if not file.filename.endswith('.tar.gz'):
            raise HTTPException(
                status_code=400, detail='The file must have a .apk extension'
            )
        file_path = UPLOAD_DIR / file.filename

        with file_path.open('wb') as buffer:
            shutil.copyfileobj(file.file, buffer)

        return JSONResponse(content={'file_name': str(file.filename)})
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post('/remove')
async def remove_archive(request: Request):
    try:
        form = await request.form()
        filename = form.get('file_name')
        if not filename or not filename.endswith(".tar.gz"):
            raise HTTPException(status_code=400, detail="Invalid file name")

        file_path = UPLOAD_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        file_path.unlink()

        return JSONResponse(content={"message": "File deleted successfully"})
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post('/profile/upload')
async def upload_profile(profile_file: UploadFile = File(...)):
    try:
        if not profile_file.filename.endswith('.txt'):
            raise HTTPException(
                status_code=400, detail='The file must have a .txt extension'
            )
        file_path = PROFILE_UPLOAD_DIR / profile_file.filename

        with file_path.open('wb') as buffer:
            shutil.copyfileobj(profile_file.file, buffer)

        return JSONResponse(content={'file_name': str(profile_file.filename)})
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e


@router.post('/profile/remove')
async def remove_profile(request: Request):
    try:
        form = await request.form()
        filename = form.get('file_name')
        if not filename or not filename.endswith(".txt"):
            raise HTTPException(status_code=400, detail="Invalid file name")

        file_path = PROFILE_UPLOAD_DIR / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        file_path.unlink()

        return JSONResponse(content={"message": "File deleted successfully"})
    except Exception as e:
        logger.exception(
            event=E.SYSTEM.API.ERROR, extra={
                "error": {"type": type(e).__name__, "msg": str(e)}
            }
        )
        raise e
