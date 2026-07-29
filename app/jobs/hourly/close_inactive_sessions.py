"""Закрытие неактивных сессий."""
from datetime import datetime, timedelta

from app.core.logger import logger, E
from app.deps import get_db
from app.models.session import SessionStatus
from app.schemas.session import SessionUpdate
from app.schemas.log import LogCreate
from app.crud.session import session
from app.jobs import registry
from app.services.log import log_service


@registry.job(
    hour="*", minute="5", id="close_inactive_sessions",
    name="Закрытие сессий, неактивных старше 24 часов"
)
async def close_inactive_sessions():
    """Закрытие сессий со статусом ACTIVE, неактивных старше 24 часов."""
    try:
        threshold_time = datetime.utcnow() - timedelta(hours=24)

        async for db in get_db():
            updated_sessions = await session.update(
                db=db,
                obj_in=SessionUpdate(status=SessionStatus.FINISHED),
                filter={
                    "status__in": [SessionStatus.ACTIVE],
                    "updated_at__lte": threshold_time
                },
                commit=False,
                returning="object"
            )
            await log_service.records(
                db,
                items=[
                    LogCreate(
                        event="session.status",
                        source="scheduler",
                        account_id=item.account_id,
                        session_id=item.id,
                        status=item.status
                    )
                    for item in updated_sessions
                ],
                commit=False
            )
            await db.commit()
            updated_count = len(updated_sessions)

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
