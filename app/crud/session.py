from collections import Counter
from typing import Any, Literal

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import set_committed_value
from sqlalchemy.orm.exc import NoResultFound

from app.crud.base import CRUDBase
from app.crud.filter.sqlalchemy import Filter
from app.models.account import Account
from app.models.session import Session
from app.schemas.session import SessionCreate, SessionUpdate, SessionFilter


class SessionCRUD(
    CRUDBase[Session, SessionCreate, SessionUpdate, SessionFilter]
):
    """CRUD-репозиторий для Session с поддержкой фильтра SessionFilter."""

    def __init__(self) -> None:
        super().__init__(model=Session, filter_class=SessionFilter)

    async def _change_counts(
        self, db: AsyncSession, deltas: dict[int, int]
    ) -> None:
        """Изменяет счётчики без commit и без изменения updated_at."""
        for account_id, delta in sorted(deltas.items()):
            if delta == 0:
                continue
            result = await db.execute(
                update(Account)
                .where(
                    Account.id == account_id,
                    Account.session_count + delta >= 0,
                )
                .values(
                    session_count=Account.session_count + delta,
                    updated_at=Account.updated_at,
                )
                .returning(Account.session_count)
                .execution_options(synchronize_session=False)
            )
            count = result.scalar_one_or_none()
            if count is None:
                await db.rollback()
                raise RuntimeError(
                    f"Не удалось изменить session_count аккаунта {account_id}"
                )

            # Обновляем уже загруженный объект фактическим значением из БД.
            key = db.sync_session.identity_key(Account, account_id)
            account = db.identity_map.get(key)
            if account is not None:
                set_committed_value(account, "session_count", count)

    async def _get_locked(
        self, db: AsyncSession, session_id: int
    ) -> Session:
        result = await db.execute(
            select(Session)
            .where(Session.id == session_id)
            .with_for_update(of=Session)
            .execution_options(populate_existing=True)
        )
        item = result.scalar_one_or_none()
        if item is None:
            raise NoResultFound(f"Session(id={session_id}) does not exist")
        return item

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: SessionCreate | dict[str, Any],
        commit: bool = True,
    ) -> Session:
        item = await super().create(db, obj_in=obj_in, commit=False)
        await self._change_counts(db, {item.account_id: 1})
        if commit:
            await db.commit()
        return item

    async def insert(
        self,
        db: AsyncSession,
        *,
        obj_list: list[SessionCreate | dict[str, Any]],
        batch_size: int = 100,
        commit: bool = True,
        returning: bool = False,
    ) -> list[Session] | None:
        items = await super().insert(
            db, obj_list=obj_list, batch_size=batch_size,
            commit=False, returning=True,
        )
        assert items is not None
        await self._change_counts(
            db, Counter(item.account_id for item in items)
        )
        if commit:
            await db.commit()
        return items if returning else None

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Session | None = None,
        id: Any | None = None,
        obj_in: SessionUpdate | dict[str, Any],
        filter: Filter | dict[str, Any] | None = None,
        commit: bool = True,
        returning: Literal["object", "id", "count"] = "object",
    ) -> Session | list[Session] | int:
        data = (
            dict(obj_in) if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
        )
        if "account_id" not in data:
            return await super().update(
                db, db_obj=db_obj, id=id, obj_in=data, filter=filter,
                commit=commit, returning=returning,
            )

        if returning not in ("object", "id", "count"):
            raise ValueError("Некорректный returning")
        if sum(value is not None for value in (db_obj, id, filter)) != 1:
            raise ValueError("Нужно передать ровно один из db_obj, id, filter")
        if filter is not None:
            raise ValueError(
                "Массовый перенос сессий запрещён; используйте update по ID"
            )

        new_account_id = data["account_id"]
        if not isinstance(new_account_id, int):
            raise ValueError("account_id должен быть целым числом")

        session_id = db_obj.id if db_obj is not None else id
        assert session_id is not None
        item = await self._get_locked(db, session_id)
        old_account_id = item.account_id
        result = await super().update(
            db, db_obj=item, obj_in=data, commit=False, returning=returning,
        )
        if old_account_id != new_account_id:
            await self._change_counts(
                db, {old_account_id: -1, new_account_id: 1}
            )
        if commit:
            await db.commit()
        return result

    async def map_update(
        self,
        db: AsyncSession,
        *,
        obj_map: dict[Any, SessionUpdate | dict[str, Any]],
        **kwargs: Any,
    ) -> list[Session] | list[Any] | int:
        for obj_in in obj_map.values():
            data = (
                obj_in if isinstance(obj_in, dict)
                else obj_in.model_dump(exclude_unset=True)
            )
            if "account_id" in data:
                raise ValueError(
                    "Перенос через map_update запрещён; "
                    "используйте update по ID"
                )
        return await super().map_update(db, obj_map=obj_map, **kwargs)

    async def delete(
        self, db: AsyncSession, *, id: int, commit: bool = True
    ) -> Session:
        item = await self._get_locked(db, id)
        result = await db.execute(
            delete(Session)
            .where(Session.id == id)
            .returning(Session.account_id)
            .execution_options(synchronize_session="fetch")
        )
        account_id = result.scalar_one()
        await self._change_counts(db, {account_id: -1})
        if commit:
            await db.commit()
        return item


session = SessionCRUD()
