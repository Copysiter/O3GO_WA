"""Завершение старых сессий."""
from datetime import datetime, timedelta

from app.core.logger import logger, E
from app.deps import get_db
from app.models.session import SessionStatus, AccountStatus
from app.schemas.session import SessionUpdate
from app.schemas.account import AccountUpdate
from app.crud.session import session
from app.crud.account import account
from app.jobs import registry


@registry.job(
    hour="*", minute="36", id="close_sessions",
    name="Закрытие сессий, неактивных старше 24 часов"
)
async def close_sessions():
    """Закрытие сессий, неактивных старше 24 часов."""
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
            
            # Извлечение уникальных account_id из обновленных сессий
            account_ids = list(set(s.account_id for s in updated_sessions))
            closed_count = len(updated_sessions)
            
            # Массовое обновление всех связанных аккаунтов батчами по 100
            if account_ids:
                batch_size = 100
                for i in range(0, len(account_ids), batch_size):
                    batch = account_ids[i:i + batch_size]
                    await account.update(
                        db=db,
                        obj_in=AccountUpdate(status=AccountStatus.AVAILABLE),
                        filter={"id__in": batch},
                        commit=False,
                        returning="count"
                    )
            
            # Зафиксировать все изменения
            await db.commit()
        
        logger.info(
            f"Завершено сессий: {closed_count}",
            event=E.SCHEDULER.JOB.SUCCESS,
            extra={"closed_count": closed_count}
        )
    except Exception as e:
        logger.exception(
            f"Ошибка при завершении старых сессий: {e}",
            event=E.SCHEDULER.JOB.ERROR
        )