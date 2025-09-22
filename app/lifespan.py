from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.adapters.db.init_db import init_db
from app.core.logger import logger, E


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом FastAPI приложения.
    """
    try:
        logger.info(
            "Запуск приложения", event=E.SYSTEM.APP.STARTUP
        )
        await init_db()
        yield
        logger.info(
            "Остановка приложения", event=E.SYSTEM.APP.SHUTDOWN
        )
    except Exception as e:
        error = {"name": type(e).__name__, "value": str(e)}
        logger.exception(
            "Системная ошибка приложения",
            event=E.SYSTEM.APP.ERROR, extra={"error": error}
        )
