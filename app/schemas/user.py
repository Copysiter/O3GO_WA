from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.user import User as UserModel
from app.crud.filter.sqlalchemy import Filter


class UserBase(BaseModel):
    """Базовая схема пользователя с общими полями"""
    name: Optional[str] = Field(
        None, description="Имя пользователя"
    )
    login: Optional[str] = Field(
        None, description="Логин для авторизаации"
    )
    ext_api_key: Optional[str] = Field(
        None, description="API ключ для внешних вызовов"
    )
    is_active: Optional[bool] = Field(
        None, description="Маркер активности пользователя"
    )
    is_superuser: bool = Field(
        None, description="Маркер прав администратора"
    )


class UserCreate(UserBase):
    """Схема для создания нового пользователя"""
    login: str = Field(None, description="Логин для авторизаации")
    password: str = Field(None, description="Пароль для авторизаации")


class UserUpdate(UserBase):
    """Схема для обновления существующего пользователя"""
    password: Optional[str] = Field(
        None, description="Пароль для авторизаации"
    )


class UserInDBBase(UserBase):
    """Базовая схема пользователя с ID, используемая при работе с БД"""
    model_config = ConfigDict(from_attributes=True)
    id: Optional[int] = Field(
        None, description="ID пользователя (автоинкремент)"
    )


# Additional properties to return via API
class User(UserInDBBase):
    """Схема пользователя, возвращаемая из API"""
    pass


# Additional properties stored in DB
class UserInDB(UserInDBBase):
    """Схема пользователя, используемая только внутри приложения"""
    hashed_password: str = Field(
        None, description="Захэшированный пароль пользователя"
    )


# List of users to return via API
class UserList(BaseModel):
    """Схема списка пользователей с общим количеством записей"""
    data: List[User]
    total: int


class UserFilter(Filter):
    """Фильтр поиска пользователей по различным полям модели"""
    id: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    name: str | None = None
    name__in: list[str] | None = None
    name__like: str | None = None

    login: str | None = None
    login__in: list[str] | None = None
    login__like: str | None = None

    x_api_key: str | None = None
    x_api_key__in: list[str] | None = None
    x_api_key__like: str | None = None

    is_active: bool | None = None
    is_superuser: bool | None = None

    order_by: Optional[list[str]] = None

    class Constants(Filter.Constants):
        model = UserModel
        ordering_field_name = "order_by"
