"""
Базовый декларативный класс для SQLAlchemy-моделей.

Назначение
----------
- Даёт единый `Base` для всех ORM-моделей.
- Автоматически формирует имя таблицы по имени класса в стиле snake_case:
"""

import re

from typing import Any
from sqlalchemy.orm import as_declarative, declared_attr  # noqa


@as_declarative()
class Base:
    """
    Базовый класс для декларативных моделей SQLAlchemy.

    Атрибуты:
        id: Заглушка для первичного ключа (конкретный тип задаётся в моделях).
        __name__: Имя класса (используется для генерации `__tablename__`).
    """
    id: Any
    __name__: str

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Генерирует имя таблицы в формате snake_case на основе имени класса.

        Логика:
            1) Разбить CamelCase на токены, с '_' в качестве разделителя.
            2) Привести к нижнему регистру.
        """
        return '_'.join(re.split(r'(?<=\w)(?=[A-Z])', cls.__name__)).lower()
