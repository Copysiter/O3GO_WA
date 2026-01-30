"""Реестр фоновых задач с декоратором для регистрации."""

from typing import Callable, Any
from functools import wraps


class JobRegistry:
    """
    Реестр для декларативной регистрации фоновых задач.
    
    Пример использования:
        @registry.job(trigger="cron", minute="*/1")
        async def my_task():
            pass
    """
    
    def __init__(self, scheduler):
        """
        Args:
            scheduler: Экземпляр AsyncIOScheduler
        """
        self.scheduler = scheduler
    
    def job(
        self,
        trigger: str = "cron",
        id: str | None = None,
        name: str | None = None,
        replace_existing: bool = True,
        **trigger_kwargs: Any
    ) -> Callable:
        """
        Декоратор для регистрации функции как фоновой задачи.
        
        Args:
            trigger: Тип триггера (по умолчанию "cron")
            id: Уникальный ID задачи (по умолчанию имя функции)
            name: Человеко-читаемое имя задачи (по умолчанию имя функции)
            replace_existing: Заменять ли существующую задачу с таким ID
            **trigger_kwargs: Параметры триггера (minute, hour, day, etc.)
        """
        def decorator(func: Callable) -> Callable:
            from app.core.logger import logger, E
            
            job_id = id or func.__name__
            job_name = name or func.__name__
            
            # Регистрация задачи в планировщике
            self.scheduler.add_job(
                func,
                trigger=trigger,
                id=job_id,
                name=job_name,
                replace_existing=replace_existing,
                **trigger_kwargs
            )
            
            logger.info(
                f"Зарегистрирована задача: {job_name} (ID: {job_id}, trigger: {trigger}, params: {trigger_kwargs})",
                event=E.SCHEDULER.JOB.REGISTER
            )
            
            @wraps(func)
            async def wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            
            return wrapper
        
        return decorator
