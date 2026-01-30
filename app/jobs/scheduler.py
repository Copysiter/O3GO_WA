"""Конфигурация AsyncIOScheduler."""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Инициализация планировщика
scheduler = AsyncIOScheduler({
    "apscheduler.timezone": "UTC",
    "apscheduler.job_defaults.coalesce": "true",
    "apscheduler.job_defaults.max_instances": "1"
})
