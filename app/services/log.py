from typing import Any, Iterable

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

import app.crud as crud
import app.models as models
import app.schemas as schemas


class LogService:
    """Сервис сохранения доменных событий."""

    STATUS_MAP = {
        "account": {
            -1: "banned",
            0: "available",
            1: "active",
            2: "paused",
        },
        "session": {
            -1: "banned",
            0: "finished",
            1: "active",
            2: "paused",
        },
        "message": {
            -1: "waiting",
            0: "created",
            1: "sent",
            2: "delivered",
            3: "undelivered",
            4: "failed",
        },
    }

    def _normalize_status(
        self, event: str, status: str | int | None
    ) -> str | None:
        if status is None:
            return None

        if isinstance(status, str) and not status.lstrip("-").isdigit():
            return status.lower()

        try:
            raw_status = int(status)
        except (TypeError, ValueError):
            return str(status).lower()

        entity = event.split(".", 1)[0]
        return self.STATUS_MAP.get(entity, {}).get(
            raw_status, str(raw_status)
        )

    def _normalize_item(
        self, item: schemas.LogCreate | dict[str, Any]
    ) -> dict[str, Any]:
        data = item.model_dump(exclude_unset=True) \
            if isinstance(item, BaseModel) else dict(item)
        if "status" in data:
            data["status"] = self._normalize_status(
                data.get("event", ""), data["status"]
            )
        return data

    async def record(
        self,
        db: AsyncSession,
        *,
        event: str,
        source: str,
        account_id: int,
        session_id: int | None = None,
        message_id: int | None = None,
        user_id: int | None = None,
        status: str | int | None = None,
        context: dict[str, Any] | None = None,
        commit: bool = False
    ) -> models.Log:
        status = self._normalize_status(event, status)
        obj_in = schemas.LogCreate(
            event=event,
            source=source,
            account_id=account_id,
            session_id=session_id,
            message_id=message_id,
            user_id=user_id,
            status=status,
            context=context or {}
        )
        return await crud.log.create(db=db, obj_in=obj_in, commit=commit)

    async def records(
        self,
        db: AsyncSession,
        *,
        items: Iterable[schemas.LogCreate | dict[str, Any]],
        commit: bool = False,
        returning: bool = False
    ) -> list[models.Log] | None:
        obj_list = [self._normalize_item(item) for item in items]
        if not obj_list:
            return [] if returning else None
        return await crud.log.insert(
            db=db, obj_list=obj_list, commit=commit, returning=returning
        )


log_service = LogService()
