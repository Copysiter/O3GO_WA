"""
Базовый CRUD-репозиторий для SQLAlchemy-моделей с поддержкой fastapi-filter.

Назначение
----------
Предоставляет типизированный класс `CRUDBase`, реализующий типовые операции
чтения/записи (get, list, count, create, update, delete). Поддерживает
пагинацию, фильтрацию и сортировку через fastapi-filter.

Использование
-------------
1) Определить Pydantic-схемы для create/update.
2) (Опционально) Определить фильтр на базе fastapi-filter.
3) Создать наследника `CRUDBase`, передав модель, (опционально) класс фильтра:

    class UserCRUD(CRUDBase[User, UserCreate, UserUpdate, UserFilter]):
        def __init__(self) -> None:
            super().__init__(model=User, filter_class=UserFilter)

    user = UserCRUD()

Примечания
----------
- Если фильтр не используется, `filter_class` можно не передавать.
- В методах, где есть параметр `filter`, можно передавать либо экземпляр
  fastapi-filter, либо словарь с полями фильтра (в этом случае он будет
  сконструирован через `filter_class(**data)`), либо `None`.
"""

from __future__ import annotations

from typing import (
    Any, Optional, Union, Literal, Dict, Generic, List, Type, TypeVar
)

from fastapi.encoders import jsonable_encoder
from fastapi_filter.contrib.sqlalchemy import Filter
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import NoResultFound
from pydantic import BaseModel

from app.adapters.db.base_class import Base


ModelType  = TypeVar("ModelType", bound=Base)
CreateType = TypeVar("CreateType", bound=BaseModel)
UpdateType = TypeVar("UpdateType", bound=BaseModel)
FilterType = TypeVar("FilterType", bound=Filter)


class CRUDBase(Generic[ModelType, CreateType, UpdateType, FilterType]):
    """
    Универсальный CRUD-репозиторий с поддержкой fastapi-filter.

    Предназначен для наследования в прикладных репозиториях.
    Модель и (опционально) класс фильтра передаются через конструктор.

    Пример:
        class TaskCRUD(CRUDBase[User, UserCreate, UserUpdate, UserFilter]):
            def __init__(self) -> None:
                super().__init__(model=User, filter_class=UserFilter)

        user = UserCRUD()
    """

    def __init__(
        self,
        *,
        model: Type[ModelType],
        filter_class: Optional[Type[FilterType]] = None
    ) -> None:
        """
        Инициализация репозитория.

        Args:
            model: SQLAlchemy-модель (класс), с которой работает репозиторий.
            filter_class: Класс фильтра (fastapi-filter). Необязателен.
        """
        self.model = model
        self.filter_class = filter_class

    # ────────────────────────────────────────────────────────────────────────
    # Вспомогательные методы
    # ────────────────────────────────────────────────────────────────────────
    def _get_filter(
        self,
        flt: Union[Filter, Dict[str, Any], None]
    ) -> Optional[Filter]:
        """
        Возвращает экземпляр фильтра fastapi-filter или None.

        Args:
            flt: Экземпляр Filter, словарь с параметрами фильтра или None.

        Returns:
            Экземпляр Filter или None.

        Raises:
            ValueError: Если `flt` — словарь, но `filter_class` не задан.
        """
        if isinstance(flt, dict):
            if self.filter_class is None:
                raise ValueError("Не задан класс фильтра (filter_class).")
            return self.filter_class(**flt)
        elif isinstance(flt, Filter):
            return flt
        return None

    # ────────────────────────────────────────────────────────────────────────
    # Базовые операции
    # ────────────────────────────────────────────────────────────────────────
    async def list(
        self,
        db: AsyncSession,
        *,
        filter: Union[Filter, Dict[str, Any], None] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[ModelType]:
        """
        Возвращает список записей с фильтрацией/сортировкой и пагинацией.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            filter: Экземпляр Filter, dict с параметрами фильтра или None.
            skip: Количество записей, которые нужно пропустить (offset).
            limit: Максимальное количество записей (limit).

        Returns:
            Список экземпляров модели.
        """
        f = self._get_filter(filter)
        stmt = select(self.model)
        if f is not None:
            stmt = f.filter(stmt)
            stmt = f.sort(stmt)
        stmt = stmt.offset(skip).limit(limit)

        res = await db.execute(stmt)
        return res.scalars().all()

    async def count(
        self,
        db: AsyncSession,
        *,
        filter: Union[Filter, Dict[str, Any], None] = None
    ) -> int:
        """
        Возвращает количество записей с учётом фильтра (если задан).

        Args:
            db: Асинхронная сессия SQLAlchemy.
            filter: Экземпляр Filter, dict с параметрами фильтра или None.

        Returns:
            Целое количество записей.
        """
        f = self._get_filter(filter)
        stmt = select(func.count(self.model.id))
        if f is not None:
            stmt = f.filter(stmt)

        res = await db.execute(stmt)
        return res.scalar_one()

    async def get(self, db: AsyncSession, id: Any) -> Optional[ModelType]:
        """
        Возвращает запись по первичному ключу `id`.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            id: Значение первичного ключа.

        Returns:
            Экземпляр модели или None, если запись не найдена.
        """
        return await db.get(self.model, id)

    async def get_by(
        self, db: AsyncSession, **kwargs: Any
    ) -> Optional[ModelType]:
        """
        Возвращает первую запись, удовлетворяющую равенству указанных полей.

        Обработка:
        - value is None  -> IS NULL;
        - value in (list/tuple/set) -> IN (...).

        Args:
            db: Асинхронная сессия SQLAlchemy.
            **kwargs: Пары поле=значение для фильтрации.

        Returns:
            Экземпляр модели или None, если запись не найдена.
        """
        stmt = select(self.model)
        for key, value in kwargs.items():
            col = getattr(self.model, key)
            if value is None:
                stmt = stmt.where(col.is_(None))
            elif (isinstance(value, (set, tuple, list))
                  and not isinstance(value, (str, bytes))):
                stmt = stmt.where(col.in_(list(value)))
            else:
                stmt = stmt.where(col == value)

        res = await db.execute(stmt.limit(1))
        return res.scalars().first()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateType,
        commit: bool = True
    ) -> ModelType:
        """
        Создаёт запись из Pydantic-модели/словаря.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            obj_in: Pydantic-модель или совместимый dict.
            commit: True — commit(), False — только flush().

        Returns:
            Созданный экземпляр модели (после flush/commit).
        """
        data = jsonable_encoder(obj_in)
        db_obj = self.model(**data)  # type: ignore[arg-type]
        db.add(db_obj)

        if commit:
            await db.commit()
            await db.refresh(db_obj)
        else:
            await db.flush()

        return db_obj

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Optional[ModelType] = None,
        id: Optional[Any] = None,
        obj_in: Union[UpdateType, Dict[str, Any]],
        filter: Union[Filter, Dict[str, Any], None] = None,
        commit: bool = True,
        returning: Literal["object", "id", "count"] = "object"
    ) -> Union[ModelType, int, List[ModelType]]:
        """
        Обновляет запись(и) с поддержкой UPDATE ... RETURNING, fastapi-filter.

        Режимы:
            1) Обновление конкретного ORM-объекта (db_obj):
               Меняет атрибуты in-place и возвращает результат.
            2) Обновление по первичному ключу (id):
               Выполняет UPDATE ... WHERE <PK>=:id RETURNING
               и возвращает согласно `returning`.
            3) Массовое обновление по фильтру (filter: Filter|dict):
               Выполняет UPDATE ... WHERE <filter> RETURNING
               и возвращает согласно `returning`.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            db_obj: Экземпляр модели для точечного обновления (режим 1).
            id: Значение первичного ключа для точечного обновления (режим 2).
            obj_in: Pydantic-модель (partial) или dict с изменениями.
            filter: Фильтр fastapi-filter (экземпляр/словарь)
                    для массового обновления (режим 3).
            commit: True — выполнить `commit()`; False — без `commit()`
            returning: Формат результата:
                - "object" — вернуть ORM-объект (список объектов);
                - "id"     — вернуть значение PK (список PK);
                - "count"  — вернуть число затронутых строк.

        Returns:
            Режим 1 (db_obj):
                - returning == "object" → ModelType
                - returning == "id"     → Any (значение PK)
                - returning == "count"  → int (=1)
            Режим 2 (id):
                - returning == "object" → ModelType
                - returning == "id"     → Any (значение PK)
                - returning == "count"  → int (0/1)
            Режим 3 (filter):
                - returning == "object" → list[ModelType]
                - returning == "id"     → list[Any]
                - returning == "count"  → int (количество строк)

        Raises:
            ValueError: Неверное значение `returning`; отсутствие `filter`
                        для массового режима; одновременное указание
                        несовместимых аргументов (`db_obj`/`id` и `filter`).
            NoResultFound: Если запись с указанным `id` не найдена.
            sqlalchemy.exc.IntegrityError: При нарушении ограничений БД.
        """
        if returning not in ("object", "id", "count"):
            raise ValueError(
                "returning must be one of: 'object', 'id', 'count'"
            )

        updates: Dict[str, Any] = (
            obj_in if isinstance(obj_in, dict) else obj_in.model_dump(
                exclude_unset=True)
        )

        # ── Режим 1: обновление ORM-экземпляра ──────────────────────────────
        if db_obj is not None and id is None and filter is None:
            current = jsonable_encoder(db_obj)
            for field in current:
                if field in updates:
                    setattr(db_obj, field, updates[field])

            db.add(db_obj)
            if commit:
                await db.commit()
                await db.refresh(db_obj)
            else:
                await db.flush()

            if returning == "object":
                return db_obj
            if returning == "id":
                return db_obj.id
            return 1

        # ── Режим 2: UPDATE ... WHERE PK=:id RETURNING ──────────────────────
        if id is not None and db_obj is None and filter is None:
            r = self.model if returning == "object" \
                else self.model.id if returning == "id" else None

            stmt = (
                update(self.model)
                .where(self.model.id == id)
                .values(**updates)
            )
            if returning is not None:
                stmt = stmt.returning(r)
            stmt = stmt.execution_options(synchronize_session=False)
            result = await db.execute(stmt)

            if returning == "object":
                objs = result.scalars().all()
                if not objs:
                    raise NoResultFound(
                        f"{self.model.__name__}(`id`={id}) does not exist"
                    )
                if commit:
                    await db.commit()
                return objs
            elif returning == "id":
                ids = [row[0] for row in result.fetchall()]
                if not ids:
                    raise NoResultFound(
                        f"{self.model.__name__}(`id`={id}) does not exist"
                    )
                if commit:
                    await db.commit()
                return ids
            else:
                count = int(result.rowcount or 0)
                if count == 0:
                    raise NoResultFound(
                        f"{self.model.__name__}(`id`={id}) does not exist"
                    )
                if commit:
                    await db.commit()
                return count

        # ── Режим 3: массовое обновление по fastapi-filter ──────────────────
        f = self._get_filter(filter)
        if f is None:
            raise ValueError(
                "You must specify either db_obj/id/filter for a bulk update."
            )

        s = f.filter(select(self.model.id))
        where_clauses = list(s._where_criteria)  # noqa

        r = self.model if returning == "objects" else self.model.id

        stmt = (
            update(self.model)
            .values(**updates)
            .where(*where_clauses)
            .returning(r)
            .execution_options(synchronize_session=False)
        )
        result = await db.execute(stmt)
        if commit:
            await db.commit()

        if returning == "object":
            return result.scalars().all()
        elif returning == "id":
            return [row[0] for row in result.fetchall()]
        else:
            return len(result.fetchall())

    async def delete(
        self, db: AsyncSession, *, id: int, commit: bool = True
    ) -> ModelType:
        """
        Удаляет запись по первичному ключу `id`.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            id: Значение первичного ключа.
            commit: True — commit(), False — flush().

        Returns:
            Удалённый экземпляр модели.

        Raises:
            NoResultFound: Если запись не найдена.
        """
        db_obj = await db.get(self.model, id)
        if db_obj is None:
            await db.rollback()
            raise NoResultFound(
                f"{self.model.__name__}(`id`={id}) does not exist"
            )
        await db.delete(db_obj)
        if commit:
            await db.commit()
        else:
            await db.flush()
        return db_obj
