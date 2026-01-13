"""
Адаптер на основе BaseFilter, собирающий SQLAlchemy-выражения из значений
полей Pydantic-фильтра.

Назначение:
- добавляет предикаты к `Select` через `.where(...)`;
- применяет сортировку через `.order_by(...)`;
- поддерживает «классические» операторы (`gt`, `in`, `lte`, `ilike`, и т.д.);
- добавляет PG JSONB-операторы: `contains` (`@>`), `any` (`?|`), `all` (`?&`);
- умеет выполнять «поиск» по нескольким полям (`search`).
"""

from enum import Enum
from typing import Callable, Dict
from pydantic import ValidationInfo, field_validator
from sqlalchemy import or_, cast, ARRAY, String
from sqlalchemy.sql import Select

from app.crud.filter.base import BaseFilter


# Реестр операторов: name -> (field, value) -> SQLAlchemy выражение
OP_HANDLERS: Dict[str, Callable] = {
    # базовые сравнения
    "eq": lambda f, v: (f == v),
    "neq": lambda f, v: (f != v),
    "gt": lambda f, v: (f > v),
    "gte": lambda f, v: (f >= v),
    "lt": lambda f, v: (f < v),
    "lte": lambda f, v: (f <= v),
    "in": lambda f, v: getattr(f, "in_")(v),
    "not_in": lambda f, v: getattr(f, "notin_")(v),
    "not": lambda f, v: getattr(f, "is_not")(v),

    # IS NULL / IS NOT NULL
    "isnull": lambda f, v: (f.is_(None) if v is True else f.is_not(None)),

    # like/ilike: добавляем % по краям, если их нет
    "like": lambda f, v: getattr(f, "like")(v if "%" in v else f"%{v}%"),
    "ilike": lambda f, v: getattr(f, "ilike")(v if "%" in v else f"%{v}%"),

    # JSONB массив содержит элемент
    "contains": lambda f, v: f.contains(
        v if isinstance(v, (dict, list)) else [v]
    ),

    # JSONB массив содержит хотя бы один из списка
    "any": lambda f, v: f.op('?|')(cast(v, ARRAY(String))),

    # JSONB массив Содержит все из списка
    "all": lambda f, v: f.op('?&')(cast(v, ARRAY(String))),
}

# Суффиксы, ожидающие список (строка из query, разделённая запятыми)
LIST_SUFFIXES = ("__in", "__not_in", "__any", "__all", "__contains")


class Filter(BaseFilter):
    """
    Адаптер фильтрации/сортировки для SQLAlchemy 2.0 (Select API):

    - принимает и возвращает Select
    - условия добавляются через .where(...)
    - поддержаны базовые операторы, like/ilike и JSONB операторы
    """

    class Direction(str, Enum):
        asc = "asc"
        desc = "desc"

    @field_validator("*", mode="before")
    def split_str(cls, value, field: ValidationInfo):
        """
        Преобразование строковых значений в списки для операторов, ожидающих
        несколько значений: __in / __not_in / __any / __all / __contains
        """

        field_name = field.field_name
        if field_name is None:
            return value

        # 1). Сортировка: список полей в одном параметре
        if field_name == cls.Constants.ordering_field_name \
                and isinstance(value, str):
            return [] if not value else list(value.split(","))

        # 2). Операторы, ожидающие "список", переданные строкой
        if isinstance(value, str) and field_name.endswith(LIST_SUFFIXES):
            return [] if not value else list(value.split(","))

        return value

    def filter(self, query: Select) -> Select:
        """
        Применяет фильтры к Select:

        - Поле без суффикса — проверка на равенство.
        - Поле с суффиксом — оператор берётся из суфикса после `__`.
        - Поле поиска (`search`) — множественный ILIKE по списку полей из
          `Constants.search_model_fields` через OR.
        - Поддержка префиксов для групп полей. Префикс снимается, затем
          применяется фильтр дочерней модели.
        """
        search_fields = getattr(self.Constants, "search_model_fields", None)

        for raw_name, value in self.filtering_fields:
            field_value = getattr(self, raw_name)

            # 1). Обработка вложенного фильтра (with_prefix)
            if isinstance(field_value, BaseFilter):
                query = field_value.filter(query)  # type: ignore[attr-defined]
                continue

            # 2). Разбор имени поля и оператора
            if "__" in raw_name:
                field_name, operator = raw_name.split("__", 1)
            else:
                field_name, operator = raw_name, "eq"

            # 3). Обработка поля поиска (множественный ILIKE через OR)
            if search_fields \
                    and field_name == self.Constants.search_field_name:
                query = query.where(or_(*[
                    getattr(self.Constants.model, f).ilike(f"%{value}%")
                    for f in search_fields
                ]))
                continue

            # 5). Применение фильтра к Select
            model_field = getattr(self.Constants.model, field_name)
            handler = OP_HANDLERS.get(operator)
            if handler is None:
                raise ValueError(f"Unsupported operator: {operator}")
            query = query.where(handler(model_field, value))

        return query

    def sort(self, query: Select) -> Select:
        """
        Применяет сортировку к Select:

        - Валидирует имена полей (с помощью `BaseFilter.validate_order_by`).
        - Интерпретирует знаки направления и добавляет `.order_by(...)`.
        """
        ordering_values = self.ordering_values
        if not ordering_values:
            return query

        for field_name in ordering_values:
            direction = (
                Filter.Direction.desc if field_name.startswith("-")
                else Filter.Direction.asc
            )
            field_name = field_name.replace("-", "").replace("+", "")

            order_by_field = getattr(self.Constants.model, field_name)
            query = query.order_by(getattr(order_by_field, direction)())

        return query
