"""
Утилиты для построения фильтров поверх Pydantic + SQLAlchemy,
адаптированные для Python 3.10+ и SQLAlchemy (2.0-стиль).

Назначение:
- Модуль обеспечивает единообразный механизм создания фильтров и сортировки
  для API на базе FastAPI.
- Решает задачу приведения query-параметров к корректным типам.
- Поддерживает автоматическую конвертацию строковых представлений списков
  (например, "1,2,3" → ["1","2","3"]).

Примечание:
Данный модуль не содержит SQL-логики (`.where()` / `.order_by()`).
SQL-часть реализуется в `adapters.sqlalchemy.filter.py`
"""

from collections.abc import Iterable
from copy import deepcopy
from typing import Any, Union, get_args, get_origin
from types import UnionType  # PEP 604 unions: int | str
from collections import Counter

from fastapi import Depends
from fastapi.exceptions import RequestValidationError
from pydantic import (
    BaseModel, ConfigDict, ValidationError, ValidationInfo,
    create_model, field_validator
)
from pydantic.fields import FieldInfo


class BaseFilter(BaseModel, extra="forbid"):
    """
    Абстрактный базовый класс Pydantic-фильтра.

    Решает задачи валидации входных параметров, сортировки и поиска (search).

    Вложенный класс `Constants` задаёт поведение фильтра:
    - `model`: ORM-модель, к которой применяется фильтр.
    - `ordering_field_name`: имя поля сортировки (по умолчанию: "order_by").
    - `ordering_fields`: белый список полей, по которым разрешена сортировка.
    - `search_model_fields`: список полей, участвующих в «поиске».
    - `search_field_name`: поле, интерпретируемое как поисковая строка.
    - `prefix` / `original_filter`: служебные атрибуты для `with_prefix()`.

    Переопределяемые методы/свойства:
    - `filter(self, query)`: применяет фильтры к запросу.
    - `sort(self, query)`: применяет сортировку к запросу.
    - `filtering_fields`: пары (поле, значение) для последующей обработки.
    """

    class Constants:  # pragma: no cover
        model: Any
        ordering_field_name: str = "order_by"
        # Белый список полей сортировки. Если None — разрешены все поля модели.
        ordering_fields: list[str] | None = None

        # Настройки поиска
        search_model_fields: list[str]
        search_field_name: str = "search"

        # Настройки для вложенных (префиксных) фильтров
        prefix: str
        original_filter: type["BaseFilter"]

    def filter(self, query):  # pragma: no cover
        """Должен применить фильтры к запросу."""
        ...

    @property
    def filtering_fields(self):
        """
        Возвращает пары (имя_поля, значение) из текущего экземпляра фильтра,
        исключая поле сортировки `Constants.ordering_field_name`.
        """
        fields = self.model_dump(exclude_none=True, exclude_unset=True)
        fields.pop(self.Constants.ordering_field_name, None)
        return fields.items()

    def sort(self, query):  # pragma: no cover
        """Должен применить сортировку к запросу."""
        ...

    @property
    def ordering_values(self):
        """
        Возвращает значение поля сортировки (например, `["-id", "name"]`).
        Бросает ошибку, если поле сортировки не объявлено в фильтре.
        """
        try:
            return getattr(self, self.Constants.ordering_field_name)
        except AttributeError as e:
            raise AttributeError(
                f"Ordering field {self.Constants.ordering_field_name}"
                f"is not defined. Make sure to add it to your filter class."
            ) from e

    @field_validator("*", mode="before", check_fields=False)
    def strip_order_by_values(cls, value, field: ValidationInfo):
        """
        Нормализует значения элементов поля сортировки (`list[str]`):
        Обрезает пробелы, удаляет пустые элементы.
        """
        if field.field_name != cls.Constants.ordering_field_name:
            return value
        if not value:
            return None
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]

    @field_validator("*", mode="before", check_fields=False)
    def validate_order_by(cls, value, field: ValidationInfo):
        """
        Валидация сортировки:

        - Поле существует в Constants.model.
        - Нет повторов (даже с разными знаками).
        - Входит в whitelist Constants.ordering_fields (если задан).
        """
        if field.field_name != cls.Constants.ordering_field_name:
            return value
        if not value:
            return None

        names = list(map(lambda s: s.lstrip("+-"), value))

        # 1) Проверка существования полей в SQLAlchemy модели
        missing = [n for n in names if not hasattr(cls.Constants.model, n)]
        if missing:
            bad = ", ".join(sorted(set(missing)))
            raise ValueError(f"{bad} is not a valid ordering field.")

        # 2) Проверка наличия дубликатов
        duplicates = [n for n, c in Counter(names).items() if c > 1]
        if duplicates:
            raise ValueError(
                f"Field names can appear at most once for "
                f"{cls.Constants.ordering_field_name}. "
                f"Duplicates: {','.join(sorted(duplicates))}."
            )

        # 3) Проверка вхождения в список разрешенных полей
        allowed = getattr(cls.Constants, "ordering_fields", None)
        if allowed:
            allowed_set = set(allowed)
            not_allowed = sorted(set(names) - allowed_set)
            if sorted(set(names) - set(allowed)):
                raise ValueError(
                    f"{', '.join(not_allowed)} is not allowed for ordering. "
                    f"Allowed: {sorted(allowed_set)}"
                )

        return value


def with_prefix(prefix: str, Filter: type[BaseFilter]) -> type[BaseFilter]:
    """
    Оборачивает существующий фильтр под заданным префиксом.

    Алгоритм:

    - Используется `alias_generator` Pydantic, который добавляет `"prefix__"`
      ко всем полям вложенного фильтра.
    - Внутренне сохраняются `Constants.original_filter` и `Constants.prefix`,
      чтобы при сборке финальной модели создавался исходный фильтр.

    Пример:
        class DeviceInnerFilter(BaseFilter):
            uid: str | None

        class DeviceFilter(BaseFilter):
            # Параметр вида: device__uid=...
            device: DeviceInnerFilter | None = FilterDepends(
                with_prefix("device", DeviceInnerFilter)
            )
    """
    class NestedFilter(Filter):  # type: ignore[misc, valid-type]
        model_config = ConfigDict(
            extra="forbid",
            alias_generator=lambda string: f"{prefix}__{string}",
        )

        class Constants(Filter.Constants):  # type: ignore[name-defined]
            ...

    NestedFilter.Constants.prefix = prefix
    NestedFilter.Constants.original_filter = Filter
    return NestedFilter


def _get_filter_type(annotation: Any) -> type[BaseFilter] | None:
    """Возвращает тип вложенного фильтра из аннотации поля."""
    origin = get_origin(annotation)

    if origin in (Union, UnionType):
        for arg in get_args(annotation):
            if arg is type(None):  # noqa: E721
                continue
            filter_type = _get_filter_type(arg)
            if filter_type is not None:
                return filter_type
        return None

    try:
        if isinstance(annotation, type) and issubclass(annotation, BaseFilter):
            return annotation
    except TypeError:
        return None

    return None


def _build_nested_filter(
    Filter: type[BaseFilter], data: dict
) -> BaseFilter:
    """Строит фильтр из плоских query-параметров с префиксами."""
    nested_params: dict[str, dict[str, Any]] = {}
    direct_params: dict[str, Any] = {}

    for key, value in data.items():
        if "__" in key:
            prefix, rest = key.split("__", 1)
            field_info = Filter.model_fields.get(prefix)
            filter_type = _get_filter_type(field_info.annotation) \
                if field_info else None

            if filter_type is not None:
                nested_params.setdefault(prefix, {})[rest] = value
                continue

        direct_params[key] = value

    for field_name, nested_data in nested_params.items():
        field_info = Filter.model_fields.get(field_name)
        filter_type = _get_filter_type(field_info.annotation) \
            if field_info else None
        if filter_type is None:
            continue

        original_filter = getattr(
            filter_type.Constants, "original_filter", None
        )
        nested_filter = original_filter or filter_type
        direct_params[field_name] = _build_nested_filter(
            nested_filter, nested_data
        )

    return Filter(**direct_params)


def _list_to_str_fields(
    Filter: type[BaseFilter],
    as_query: bool = False,
    prefix: str | None = None,
):
    """
    Создаёт копию схемы фильтра, где поля-списки (`list[...]`) заменяются на
    строки с элементами, разделёнными запятыми.

    Используется для генерации схемы, совместимой с query-параметрами FastAPI.
    Поля `list[...] | None` приводятся к `str | None`, значения по умолчанию,
    если они итерируемые, преобразуются в строку
    """
    result: dict[str, tuple[type | object, FieldInfo | None]] = {}

    for name, f in Filter.model_fields.items():
        if prefix is not None and name == Filter.Constants.ordering_field_name:
            continue

        filter_type = _get_filter_type(f.annotation)
        if filter_type is not None:
            original_filter = getattr(
                filter_type.Constants, "original_filter", None
            )
            nested_filter = original_filter or filter_type
            nested_prefix = getattr(filter_type.Constants, "prefix", name)
            field_prefix = f"{prefix}__{nested_prefix}" \
                if prefix else nested_prefix
            result.update(_list_to_str_fields(
                nested_filter, as_query=as_query, prefix=field_prefix
            ))
            continue

        field = deepcopy(f)
        annotation = f.annotation
        field_name = f"{prefix}__{name}" if prefix else name

        # Удаляет None из аннотации типа
        origin = get_origin(annotation)
        if origin in (Union, UnionType):
            args = [a for a in get_args(annotation) if
                    a is not type(None)]  # noqa: E721
            if len(args) == 1:
                ann = args[0]
                origin = get_origin(ann)

        # Преобразование типа list[...] в str | None
        is_list = (annotation is list) or (origin is list)
        if is_list and as_query:
            d = field.default
            if isinstance(d, Iterable) and not isinstance(d, (str, bytes)):
                field.default = ",".join(map(str, d))
            result[field_name] = (
                str if f.is_required() else (str | None), field
            )
        else:
            result[field_name] = (f.annotation, field)

    return result


def FilterDepends(
    Filter: type[BaseFilter], *,
    by_alias: bool = False, as_query: bool = False
) -> Any:
    """
    FastAPI-обёртка для фильтров, позволяющая передавать list-поля в query.

    Алгоритм:

    - Создаётся временная схема, где list-поля заменены на строки.
    - FastAPI парсит запрос в эту модель.
    - Пересобираем исходный фильтр `Filter(**data)` — Pydantic превращает
      строки `'a,b,c'` обратно в `list[T]` по аннотациям фильтра.
    - Если фильтр создан через `with_prefix`, снимаем префикс и строит
      `Constants.original_filter`.
    """
    fields = _list_to_str_fields(Filter, as_query=as_query)
    GeneratedFilter: type[BaseFilter] = create_model(
        Filter.__class__.__name__, **fields
    )

    class FilterWrapper(GeneratedFilter):  # type: ignore[misc,valid-type]
        def __new__(cls, **kwargs):
            try:
                # 1). Создание временной схемы
                instance = GeneratedFilter(**kwargs)

                # 2). Подготовка данных для исходной модели фильтра
                data = instance.model_dump(
                    exclude_unset=True,
                    exclude_defaults=True,
                    by_alias=by_alias,
                )

                # 3). Обработка фильтров, созданных через with_prefix
                original_filter = getattr(
                    Filter.Constants, "original_filter", None
                )
                if original_filter is not None:
                    prefix = f"{Filter.Constants.prefix}__"
                    stripped = {
                        k.removeprefix(prefix): v for k, v in data.items()
                    }
                    return original_filter(**stripped)

                # 4). Конструирование исходного фильтра с учетом вложенности
                return _build_nested_filter(Filter, data)

            except ValidationError as e:
                raise RequestValidationError(e.errors()) from e

    return Depends(FilterWrapper)
