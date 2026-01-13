from secrets import token_urlsafe
from typing import Optional, Union, Literal, Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserFilter
from app.crud.base import CRUDBase
from app.crud.filter.sqlalchemy import Filter


class UserCRUD(
    CRUDBase[User, UserCreate, UserUpdate, UserFilter]
):
    """CRUD-репозиторий для User с поддержкой фильтра UserFilter."""

    def __init__(self) -> None:
        super().__init__(model=User, filter_class=UserFilter)

    async def create(
        self,
        db: AsyncSession,
        *,
        obj_in: UserCreate,
        commit: bool = True,
    ) -> User:
        """
        Создаёт пользователя с предобработкой полезной нагрузки.

        Логика подготовки:
            - `password` преобразуется в `hashed_password`;
            - если `ext_api_key` не задан, генерируется `token_urlsafe(32)`.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            obj_in: Pydantic-модель `UserCreate` с данными пользователя.
            commit: Если `True` — вызывается `commit()` и `refresh()`,
                    иначе только `flush()`.

        Returns:
            User: Созданный экземпляр модели.

        Raises:
            sqlalchemy.exc.IntegrityError: При нарушении уникальности
                                           (`login`, `ext_api_key` и т.п.).
        """
        data: Dict[str, Any] = obj_in.model_dump(exclude_unset=True)

        pwd = data.pop("password", None)
        if pwd:
            data["hashed_password"] = get_password_hash(pwd)

        if not data.get("ext_api_key"):
            data["ext_api_key"] = token_urlsafe(32)

        return await super().create(db, obj_in=data, commit=commit)

    async def update(
        self,
        db: AsyncSession,
        *,
        db_obj: Optional[User] = None,
        id: Optional[Any] = None,
        obj_in: Union[UserUpdate, Dict[str, Any]],
        filter: Union[Filter, Dict[str, Any], None] = None,
        commit: bool = True,
        returning: Literal["object", "id", "count"] = "object"
    ) -> Union[User, int, List[User], Any, List[Any]]:
        """
        Обновляет пользователя(ей) с предобработкой данных пользователя.

        Поддерживаемые режимы (см. `CRUDBase.update`):
            1) Точечное обновление переданного ORM-объекта (`db_obj`).
            2) Точечное обновление по первичному ключу (`id`).
            3) Массовый апдейт по фильтру (`filter`: fastapi-filter или dict).

        Логика подготовки:
            - если в `obj_in` присутствует `password`, он хешируется;
            - если `ext_api_key` явно передан как `None`, поле игнорируется.

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
            Union[User, int, List[User], Any, List[Any]]:
                Зависит от режима и `returning`:
                - режим `db_obj`: `User` | `id` | 1
                - режим `id`:     `User` | `id` | 0/1
                - режим `filter`: list[User] | list[id] | count

        Raises:
            ValueError: Неверное значение `returning`; отсутствие `filter`
                        для массового режима; одновременное указание
                        несовместимых аргументов (`db_obj`/`id` и `filter`).
            NoResultFound: Если запись с указанным `id` не найдена.
            sqlalchemy.exc.IntegrityError: При нарушении ограничений БД.
        """
        updates: Dict[str, Any] = (
            obj_in if isinstance(obj_in, dict)
            else obj_in.model_dump(exclude_unset=True)
        )

        if "password" in updates:
            pwd = updates.pop("password")
            if pwd:
                updates["hashed_password"] = get_password_hash(pwd)

        if updates.get("ext_api_key", "__MISSING__") is None:
            updates.pop("ext_api_key", None)

        return await super().update(
            db, db_obj=db_obj, id=id, obj_in=updates, filter=filter,
            commit=commit, returning=returning
        )

    async def authenticate(
        self, db: AsyncSession, *, login: str, password: str
    ) -> Optional[User]:
        """
        Аутентифицирует пользователя по логину и паролю.

        Args:
            db: Асинхронная сессия SQLAlchemy.
            login: Логин пользователя.
            password: Пароль в открытом виде.

        Returns:
            Optional[User]: ORM-объект пользователя или `None`.
        """
        user = await self.get_by(db, login=login)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def is_active(self, user: User) -> bool:
        """
        Возвращает признак активности пользователя.

        Args:
            user: ORM-объект `User`.

        Returns:
            bool: `True`, если пользователь активен; иначе `False`.
        """
        return user.is_active

    def is_superuser(self, user: User) -> bool:
        """
        Возвращает признак суперпользователя.

        Args:
            user: ORM-объект `User`.

        Returns:
            bool: `True`, если есть права суперпользователя; иначе `False`.
        """
        return user.is_superuser


user = UserCRUD()
