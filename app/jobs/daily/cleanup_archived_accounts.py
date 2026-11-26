"""Retry file cleanup without deleting account history."""
from app.adapters.db.session import async_session
from app.jobs import registry
from app.services.account_archive import retry_archived_files


@registry.job(hour=0, minute=0, id="cleanup_archived_accounts",
              name="Удаление файлов архивированных аккаунтов")
async def cleanup_archived_accounts():
    async with async_session() as db:
        await retry_archived_files(db)
