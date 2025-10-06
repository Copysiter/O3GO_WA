"""
Инициализация базы данных и создание первичного суперпользователя.

Назначение
----------
Модуль содержит три корневые функции:
- `init_models()` — управляет жизненным циклом схемы БД: при необходимости
  выполняет `drop_all` и/или `create_all` на основании настроек.
- `create_superuser()` — создаёт первичного суперпользователя.
- `init_db()` — init_models()`, затем `create_superuser()`.
"""

import app.schemas as schemas
import app.crud as crud

from app.core.settings import settings
from app.core.logger import logger, E
from app.adapters.db.base_class import Base
from app.adapters.db.session import engine, async_session


async def create_superuser() -> None:
    """
    Создаёт первичного суперпользователя, если пользователь с логином
    `settings.FIRST_SUPERUSER` отсутствует.

    Исключения:
        Любые исключения перехватываются и логируются через
        `logger.exception(..., event=E.SYSTEM.APP.ERROR)`, чтобы не
        блокировать запуск приложения.

    Возвращает:
        None
    """
    async with async_session() as session:
        try:
            user = await crud.user.get_by(
                session,
                login=settings.FIRST_SUPERUSER
            )
            if not user:
                user_in = schemas.UserCreate(
                    login=settings.FIRST_SUPERUSER,
                    name='Admin',
                    password=settings.FIRST_SUPERUSER_PASSWORD,
                    is_active=True,
                    is_superuser=True,
                )
                await crud.user.create(session, obj_in=user_in)
        except Exception as e:
            error = {"name": type(e).__name__, "value": str(e)}
            logger.exception(
                "Ошибка создания пользователя",
                event=E.SYSTEM.APP.ERROR, extra={"error": error}
            )


async def init_models() -> None:
    """
    Инициализирует схему базы данных согласно настройкам.

    Поведение:
        - `settings.DATABASE_DELETE_ALL` == True — выполняется `drop_all`.
        - `settings.DATABASE_CREATE_ALL` == True — выполняется `create_all`.
    """
    async with engine.begin() as conn:
        if settings.DATABASE_DELETE_ALL:
            await conn.run_sync(Base.metadata.drop_all)
        if settings.DATABASE_CREATE_ALL:
            await conn.run_sync(Base.metadata.create_all)


async def init_db() -> None:
    """
    Комплексная инициализация базы данных при старте приложения.

    Последовательность:
        1) `init_models()` — приведение схемы БД к требуемому состоянию.
        2) `create_superuser()` — обеспечение наличия суперпользователя.

    Возвращает:
        None
    """
    await init_models()
    await create_superuser()
