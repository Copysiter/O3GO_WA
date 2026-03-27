"""Освобождение неактивных аккаунтов."""
from datetime import datetime, timedelta

from app.core.logger import logger, E
from app.deps import get_db
from app.models.session import AccountStatus
from app.schemas.account import AccountUpdate
from app.crud.account import account
from app.jobs import registry


@registry.job(
    hour="*", minute="0", id="close_inactive_accounts",
    name="Освобождение аккаунтов, неактивных старше 24 часов"
)
async def close_inactive_accounts():
    """Освобождение аккаунтов со статусом ACTIVE, неактивных старше 24 часов."""
    try:
        threshold_time = datetime.utcnow() - timedelta(hours=24)

        async for db in get_db():
            updated_count = await account.update(
                db=db,
                obj_in=AccountUpdate(status=AccountStatus.AVAILABLE),
                filter={
                    "status__in": [AccountStatus.ACTIVE],
                    "updated_at__lte": threshold_time
                },
                commit=True,
                returning="count"
            )

        logger.info(
            f"Освобождено аккаунтов: {updated_count}",
            event=E.SCHEDULER.JOB.SUCCESS,
            extra={"updated_accounts": updated_count}
        )
    except Exception as e:
        logger.exception(
            f"Ошибка при освобождении неактивных аккаунтов: {e}",
            event=E.SCHEDULER.JOB.ERROR
        )
