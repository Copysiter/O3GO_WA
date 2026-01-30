from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.adapters.db.init_db import init_db
from app.core.logger import logger, E
from app.jobs import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Контекстный менеджер для управления жизненным циклом FastAPI приложения.
    """
    try:
        logger.info(event=E.SYSTEM.APP.STARTUP)
        await init_db()
        
        # Запуск планировщика фоновых задач
        logger.info(event=E.SCHEDULER.SERVICE.STARTUP)
        scheduler.start()
        
        # Логирование зарегистрированных задач
        jobs = scheduler.get_jobs()
        logger.info(
            f"Планировщик запущен. Зарегистрировано задач: {len(jobs)}",
            event=E.SCHEDULER.SERVICE.SUCCESS,
            extra={
                "jobs_count": len(jobs), "jobs": [{
                    "id": j.id, "name": j.name,
                    "next_run": str(j.next_run_time)
                } for j in jobs]
            }
        )
        
        yield
        
        # Остановка планировщика
        scheduler.shutdown(wait=True)
        logger.info(event=E.SCHEDULER.SERVICE.SHUTDOWN)
        
        logger.info(
            "Остановка приложения", event=E.SYSTEM.APP.SHUTDOWN
        )
    except Exception as e:
        error = {"name": type(e).__name__, "value": str(e)}
        logger.exception(
            "Системная ошибка приложения",
            event=E.SYSTEM.APP.ERROR, extra={"error": error}
        )
