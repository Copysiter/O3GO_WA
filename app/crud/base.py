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

from typing import (
    Any, Optional, Literal, Dict, Generic, List, Type, TypeVar, Sequence, cast
)

from sqlalchemy import func, select, insert, update, bindparam, case, Boolean
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import NoResultFound
from pydantic import BaseModel

from app.adapters.db.base_class import Base
from app.crud.filter.sqlalchemy import Filter


ModelType = TypeVar("ModelType", bound=Base)
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
        flt: Filter | Dict[str, Any] | None
    ) -> Filter | None:
        """
        Возвращает экземпляр фильтра fastapi-filter или None.

        Args:
            flt: Экземпляр Filter, словарь с параметрами фильтра или None.

        Returns:
            Filter | None: Экземпляр Filter или None.

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
    async def all(
        self,
        db: AsyncSession,
        *,
        filter: Filter | Dict[str, Any] | None = None
    ) -> Sequence[ModelType]:
        """
        Возвращает все записи с фильтрацией/сортировкой.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            filter: Экземпляр Filter, dict с параметрами фильтра или None.

        Returns:
            list: Список экземпляров модели.
        """
        f = self._get_filter(filter)
        stmt = select(self.model)
        if f is not None:
            stmt = f.filter(stmt)
            stmt = f.sort(stmt)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def list(
        self,
        db: AsyncSession,
        *,
        filter: Filter | Dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100
    ) -> Sequence[ModelType]:
        """
        Возвращает список записей с фильтрацией/сортировкой и пагинацией.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            filter: Экземпляр Filter, dict с параметрами фильтра или None.
            skip: Количество записей, которые нужно пропустить (offset).
            limit: Максимальное количество записей (limit).

        Returns:
            list: Список экземпляров модели.
        """
        f = self._get_filter(filter)
        stmt = select(self.model)
        if f is not None:
            stmt = f.filter(stmt)
            stmt = f.sort(stmt)
        stmt = stmt.offset(skip).limit(limit)

        result = await db.execute(stmt)
        return result.scalars().all()

    async def count(
        self,
        db: AsyncSession,
        *,
        filter: Filter | Dict[str, Any] | None = None
    ) -> int:
        """
        Возвращает количество записей с учётом фильтра (если задан).

        Args:
            db: Асинхронная сессия SQLAlchemy.
            filter: Экземпляр Filter, dict с параметрами фильтра или None.

        Returns:
            int: Количество записей.
        """
        f = self._get_filter(filter)
        stmt = select(func.count(self.model.id))
        if f is not None:
            stmt = f.filter(stmt)

        result = await db.execute(stmt)
        return result.scalar_one()

    async def get(self, db: AsyncSession, id: Any) -> ModelType | None:
        """
        Возвращает запись по первичному ключу `id`.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            id: Значение первичного ключа.

        Returns:
            ModelType | None: Экземпляр модели или None.
        """
        return await db.get(self.model, id)

    async def get_by(
        self, db: AsyncSession, **kwargs: Any
    ) -> ModelType | None:
        """
        Возвращает первую запись, удовлетворяющую равенству указанных полей.

        Обработка:
        - value is None  -> IS NULL;
        - value in (list/tuple/set) -> IN (...).

        Args:
            db: Асинхронная сессия SQLAlchemy.
            **kwargs: Пары поле=значение для фильтрации.

        Returns:
            ModelType | None: Экземпляр модели или None.
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

        result = await db.execute(stmt.limit(1))
        return result.scalars().first()

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateType | Dict[str, Any],
        commit: bool = True
    ) -> ModelType:
        """
        Создаёт запись из Pydantic-модели/словаря.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            obj_in: Pydantic-модель или совместимый словарь.
            commit: True — выполнить `commit()`; False — без `commit()`

        Returns:
            ModelType: Созданный экземпляр модели (после flush/commit).
        """
        data = (
            obj_in if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
        )
        db_obj = self.model(**data)  # type: ignore[arg-type]
        db.add(db_obj)

        if commit:
            await db.commit()
        else:
            await db.flush()

        await db.refresh(db_obj)

        return db_obj

    async def insert(
        self,
        db: AsyncSession,
        *,
        obj_list: List[CreateType | Dict[str, Any]],
        batch_size: int = 100,
        commit: bool = True,
        returning: bool = False
    ) -> List[ModelType] | None:
        """
        Массовое добавление записей с батчингом.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            obj_list: Список Pydantic-моделей или словарей.
            batch_size: Размер батча (по умолчанию 100).
            commit: True — выполнить `commit()`; False — без `commit()`
            returning: Если True, возвращает созданные ORM-объекты.

        Returns:
            list | None: Список созданных экземпляров модели или None.

        Raises:
            sqlalchemy.exc.IntegrityError: При нарушении ограничений БД.
        """
        data = [
            obj_in if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
            for obj_in in obj_list
        ]

        result: List[ModelType] = []

        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            stmt = insert(self.model).values(batch)
            if returning:
                stmt = stmt.returning(self.model)
                res = await db.execute(stmt)
                result.extend(res.scalars().all())
            else:
                await db.execute(stmt)

        if commit:
            await db.commit()
        else:
            await db.flush()

        return result if returning else None

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Optional[ModelType] = None,
        id: Optional[Any] = None,
        obj_in: UpdateType | Dict[str, Any],
        filter: Filter | Dict[str, Any] | None = None,
        commit: bool = True,
        returning: Literal["object", "id", "count"] = "object"
    ) -> ModelType | List[ModelType] | int:
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
            obj_in: Pydantic-модель или совместимый словарь.
            filter: Фильтр fastapi-filter (экземпляр/словарь)
                    для массового обновления (режим 3).
            commit: True — выполнить `commit()`; False — без `commit()`
            returning: Формат возвращаемого результата.

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
            sqlalchemy.exc.IntegrityError: При нарушении ограничений БД.
        """
        if returning not in ("object", "id", "count"):
            raise ValueError(
                "`returning` must be one of: 'object', 'id', 'count'."
            )
        if sum(x is not None for x in (db_obj, id, filter)) > 1:
            raise ValueError(
                "Only one of `db_obj` | `id` | `filter` may be set."
            )

        updates: Dict[str, Any] = (
            obj_in if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
        )

        # Режим 1: обновление ORM-экземпляра
        if db_obj is not None and id is None and filter is None:
            for k, v in updates.items():
                setattr(db_obj, k, v)
            db.add(db_obj)
            if commit:
                await db.commit()
            else:
                await db.flush()

            await db.refresh(db_obj)

            return db_obj if returning == "object" \
                else db_obj.id if returning == "id" else 1

        # Режимы 2 и 3: единый конструктор WHERE
        single = id is not None
        if single:
            where_clauses = [self.model.id == id]
        else:
            f = self._get_filter(filter)
            if f is None:
                raise ValueError("Filter must be provided for bulk update.")
            s = f.filter(select(self.model.id))
            where_clauses = list(s._where_criteria)  # noqa

        # Общий UPDATE с корректным RETURNING
        stmt = (
            update(self.model)
            .values(**updates)
            .where(*where_clauses)
            .execution_options(synchronize_session=False)
        )

        if returning == "object":
            stmt = stmt.returning(self.model)
        elif returning == "id":
            stmt = stmt.returning(self.model.id)

        res = await db.execute(stmt)

        # Формирование ответа
        if returning == "count":
            result = int(res.rowcount or 0)
        else:
            result = res.scalars().first() \
                if single else res.scalars().all()  # type: ignore

        if commit:
            await db.commit()
        else:
            await db.flush()

        # Refresh только если db_obj был передан (режим 1)
        if db_obj is not None:
            await db.refresh(db_obj)

        return result

    async def map_update(
        self,
        db: AsyncSession,
        *,
        key: str = "id",
        obj_map: Dict[Any, UpdateType | Dict[str, Any]],
        batch_size: int = 100,
        commit: bool = True,
        returning: Literal["object", "id", "count"] = "count",
    ) -> List[ModelType] | List[Any] | int:
        """
        Массово обновляет записи по словарю «ключ → набор полей» батчами.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            key: Имя колонки для сопоставления (WHERE <key>=:k).
            obj_map: {значение ключа: UpdateType | dict}.
            commit: True — выполнить `commit()`; False — без `commit()`
            batch_size: Размер батча для executemany.
            returning: Формат возвращаемого результата.

        Returns:
            list | int — согласно `returning`.
        """
        if not obj_map:
            return 0 if returning == "count" else []

        model = self.model
        key_col = getattr(model, key)

        updates = {
            k: (v if isinstance(v, dict)
                else v.model_dump(exclude_unset=True))
            for k, v in obj_map.items()
        }

        fields: List[str] = list({
            f for upd in updates.values() for f in upd.keys()
        })
        if not fields:
            return 0 if returning == "count" else []

        values_clause: Dict[str, Any] = {}
        for field in fields:
            col = getattr(model, field)
            values_clause[field] = case((
                bindparam(f"h_{field}", type_=Boolean, value=False),
                bindparam(f"v_{field}", type_=col.type, required=False)
            ), else_=col)

        stmt = (
            update(model)
            .where(key_col == bindparam("k", type_=key_col.type))
            .values(values_clause)
            .execution_options(synchronize_session=False)
        )

        if returning == "object":
            stmt = stmt.returning(model)
        elif returning == "id":
            stmt = stmt.returning(model.id)

        objects: List[ModelType] = []
        ids: List[Any] = []
        total = 0

        items = list(updates.items())
        for i in range(0, len(items), batch_size):
            batch = items[i: i + batch_size]

            payload: List[Dict[str, Any]] = []
            for k, upd in batch:
                params: Dict[str, Any] = {"k": k}
                for field, val in upd.items():
                    params[f"h_{field}"] = True
                    params[f"v_{field}"] = val
                payload.append(params)

            res = await db.execute(stmt, payload)

            if returning == "object":
                objects.extend(res.scalars().all())
            elif returning == "id":
                ids.extend(res.scalars().all())
            else:
                total += int(res.rowcount or 0)

        if commit:
            await db.commit()
        else:
            await db.flush()

        result = objects if returning == "object" \
            else ids if returning == "id" else total

        return result

    async def upsert(
        self,
        db: AsyncSession,
        *,
        obj_in: CreateType | UpdateType | Dict[str, Any],
        match: List[str] | str,
        commit: bool = True
    ) -> ModelType | List[ModelType] | int:
        """
        Создает новую запись или обновляет существующую.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            obj_in: Pydantic-модель или совместимый словарь.
            match: Поле или список полей для поиска существующей записи.
            commit: True — выполнить `commit()`; False — без `commit()`

        Returns:
            ModelType: Созданный или обновленный экземпляр модели.
        """
        data: Dict[str, Any] = (
            obj_in if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
        )

        match_fields = [match] if isinstance(match, str) else match

        for field in match_fields:
            if field not in data:
                raise ValueError(
                    f"Match field '{field}' must be present in data."
                )

        db_obj = await self.get_by(db, **{
            field: data[field] for field in match_fields
        })

        if db_obj is not None:
            return await self.update(
                db, db_obj=db_obj, obj_in=data, commit=commit
            )

        return await self.create(
            db,
            obj_in=cast(CreateType | Dict[str, Any], obj_in),
            commit=commit
        )

    async def delete(
        self, db: AsyncSession, *, id: int, commit: bool = True
    ) -> ModelType:
        """
        Удаляет запись по первичному ключу `id`.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            id: Значение первичного ключа.
            commit: True — выполнить `commit()`; False — без `commit()`

        Returns:
            ModelType: Удалённый экземпляр модели.

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
