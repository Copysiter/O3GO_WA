from typing import List
from pydantic import BaseModel, Field

from app.crud.filter.sqlalchemy import Filter
from app.models.version import Version as VersionModel

class VersionBase(BaseModel):
    """Базовая схема версии Android приложения"""
    file_name: str | None = Field(None, description="Название APK файла")
    description: str | None = Field(None, description="Описание версии APK")


class VersionCreate(VersionBase):
    """Схема для создания новой версии Android приложения"""
    file_name: str = Field(None, description="Название APK файла")


class VersionUpdate(VersionBase):
    """Схема для обновления существующей версии Android приложения"""
    pass


class VersionInDBBase(VersionBase):
    """
    Базовая схема версии Android приложения, используемая при работе с БД
    """
    id: int = Field(None, description="Уникальный идентификатор")

    class Config:
        from_attributes = True


class Version(VersionInDBBase):
    """Схема версии Android приложения, возвращаемая из API"""
    pass


class VersionInDB(VersionInDBBase):
    """Схема версии Android приложения для внутреннего использования"""
    pass


class VersionRows(BaseModel):
    """Схема списка версий Android приложения с общим количеством записей"""
    data: List[Version]
    total: int = 0


class VersionFilter(Filter):
    """Фильтр поиска версий Android приложения по различным полям модели"""
    id: int | None = None
    id__neq: int | None = None
    id__in: list[int] | None = None
    id__gt: int | None = None
    id__lt: int | None = None

    file_name: str | None = None
    file_name__neq: str | None = None
    file_name__in: list[str] | None = None
    file_name__ilike: str | None = None

    description_name: str | None = None
    description__neq: str | None = None
    description__in: list[str] | None = None
    description__ilike: str | None = None

    order_by: list[str] | None = None

    class Constants(Filter.Constants):
        model = VersionModel

        # имя поля сортировки, совпадающий с атрибутом схемы
        ordering_field_name = "order_by"
