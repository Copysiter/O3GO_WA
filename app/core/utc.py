"""Shared RFC 3339 validation for settings and API read models."""

import re
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, AwareDatetime, BeforeValidator


_RFC3339 = re.compile(
    r"\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:[Zz]|[+-]\d{2}:\d{2})"
)


def _require_datetime(value: Any) -> Any:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and _RFC3339.fullmatch(value):
        return value
    raise ValueError("Use an RFC 3339 datetime with an explicit timezone")


def _to_utc(value: datetime) -> datetime:
    try:
        return value.astimezone(UTC)
    except (OverflowError, ValueError) as error:
        raise ValueError(
            "Datetime is outside the supported UTC range"
        ) from error


UTCDateTime = Annotated[
    AwareDatetime, BeforeValidator(_require_datetime), AfterValidator(_to_utc),
]
