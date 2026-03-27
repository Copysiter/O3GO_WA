"""Закрытие неактивных сессий."""
from datetime import datetime, timedelta

from app.core.logger import logger, E
from app.deps import get_db
from app.models.session import SessionStatus
from app.schemas.session import SessionUpdate
from app.crud.session import session
from app.jobs import registry


@registry.job(
    hour="*", minute="5", id="close_inactive_sessions",
    name="Закрытие сессий, неактивных старше 24 часов"
)
async def close_inactive_sessions():
    """Закрытие сессий со статусом ACTIVE, неактивных старше 24 часов."""
    try:
        threshold_time = datetime.utcnow() - timedelta(hours=24)

        async for db in get_db():
            updated_count = await session.update(
                db=db,
                obj_in=SessionUpdate(status=SessionStatus.FINISHED),
                filter={
                    "status__in": [SessionStatus.ACTIVE],
                    "updated_at__lte": threshold_time
                },
                commit=True,
                returning="count"
            )

        logger.info(
            f"Закрыто сессий: {updated_count}",
            event=E.SCHEDULER.JOB.SUCCESS,
            extra={"closed_sessions": updated_count}
        )
    except Exception as e:
        logger.exception(
            f"Ошибка при закрытии неактивных сессий: {e}",
            event=E.SCHEDULER.JOB.ERROR
        )
