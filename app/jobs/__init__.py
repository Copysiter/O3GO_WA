"""Модуль фоновых задач на основе APScheduler."""

from .scheduler import scheduler
from .registry import JobRegistry

# Создание глобального экземпляра реестра
registry = JobRegistry(scheduler)

# Импорт модулей с задачами (это активирует декораторы)
from . import minutely  # noqa: F401
from . import hourly    # noqa: F401
from . import daily     # noqa: F401

__all__ = ["scheduler", "registry"]