"""Request and read-model contracts for service statistics."""

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.core.utc import UTCDateTime


MIN_STATS_DATE = datetime(1900, 1, 1, tzinfo=UTC)


def _require_user_id(value: Any) -> Any:
    if type(value) is int:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        return value
    raise ValueError("User ID must be a positive integer")


StatsUserId = Annotated[
    int, Field(gt=0, le=2147483647), BeforeValidator(_require_user_id),
]
StatsCount = Annotated[int, Field(ge=0, strict=True)]
StatsGranularity = Literal["hour", "day"]
StatsCoverageState = Literal["recorded", "partial", "unavailable"]
StatsMessageStatusName = Literal["sent", "delivered", "undelivered", "failed"]


class StatsModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=True,
    )


class StatsLiveQuery(StatsModel):
    user_id: StatsUserId | None = None


class StatsSummaryQuery(StatsLiveQuery):
    start_at: UTCDateTime
    end_at: UTCDateTime | None = None

    @field_validator("start_at", "end_at")
    @classmethod
    def validate_minimum_date(cls, value: datetime | None) -> datetime | None:
        if value is not None and value < MIN_STATS_DATE:
            raise ValueError(
                "The reporting period cannot begin before 1900 UTC"
            )
        return value


class StatsScope(StatsModel):
    user_id: StatsUserId | None
    mode: Literal["all", "user"]
    label: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_scope(self) -> Self:
        if (self.mode == "all") != (self.user_id is None):
            raise ValueError("Only an all-user scope can have a null user ID")
        return self


class StatsComparison(StatsModel):
    start_at: UTCDateTime
    end_at: UTCDateTime


class StatsPeriod(StatsModel):
    start_at: UTCDateTime
    end_at: UTCDateTime | None
    effective_end_at: UTCDateTime
    granularity: StatsGranularity
    comparison: StatsComparison


class StatsMetrics(StatsModel):
    # Required nullable fields distinguish unavailable data from omitted
    # metrics.
    opened: StatsCount | None
    finished: StatsCount | None
    session_bans: StatsCount | None
    account_bans: StatsCount | None
    sent: StatsCount | None
    delivered: StatsCount | None
    undelivered: StatsCount | None
    failed: StatsCount | None
    account_errors: StatsCount | None
    session_errors: StatsCount | None
    auto_finished: StatsCount | None
    message_created: StatsCount | None


class StatsTrendPoint(StatsMetrics):
    key: UTCDateTime
    from_at: UTCDateTime
    to_at: UTCDateTime


class StatsMessageStatus(StatsModel):
    status: StatsMessageStatusName
    value: StatsCount


class StatsSessionStatus(StatsModel):
    status: Literal["opened", "finished", "banned"]
    value: StatsCount | None


class StatsMessageCohort(StatsModel):
    total: StatsCount
    created: StatsCount
    waiting: StatsCount
    unknown_status: StatsCount


class StatsDelivery(StatsModel):
    delivered: StatsCount
    terminal: StatsCount
    rate: Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)] | None

    @model_validator(mode="after")
    def validate_delivery(self) -> Self:
        if self.delivered > self.terminal:
            raise ValueError(
                "Delivered messages cannot exceed terminal outcomes"
            )
        if (self.terminal == 0) != (self.rate is None):
            raise ValueError(
                "Delivery rate is null exactly when terminal is zero"
            )
        return self


class StatsCoverageGroup(StatsModel):
    """Quality of retained counts, not completeness of event collection.

    Recorded means retained data is countable, including zero events.
    Partial with missing_operation_id masks the affected error group/period.
    """

    from_at: UTCDateTime | None = Field(
        alias="from",
        description="Always null: no observed collection start date is known.",
    )
    current_state: StatsCoverageState
    previous_state: StatsCoverageState
    current_reason: str | None = None
    previous_reason: str | None = None


class StatsCoverage(StatsModel):
    lifecycle: StatsCoverageGroup
    message_events: StatsCoverageGroup
    account_errors: StatsCoverageGroup
    session_errors: StatsCoverageGroup


class StatsSummary(StatsPeriod):
    generated_at: UTCDateTime
    scope: StatsScope
    totals: StatsMetrics
    previous: StatsMetrics
    trend: list[StatsTrendPoint] = Field(max_length=32)
    statuses: list[StatsMessageStatus] = Field(min_length=4, max_length=4)
    message_cohort: StatsMessageCohort
    session_statuses: list[StatsSessionStatus] = Field(
        min_length=3, max_length=3,
    )
    delivery: StatsDelivery
    coverage: StatsCoverage

    @field_validator("statuses", "session_statuses")
    @classmethod
    def validate_unique_statuses(
        cls, values: list[StatsMessageStatus] | list[StatsSessionStatus],
    ) -> list[StatsMessageStatus] | list[StatsSessionStatus]:
        if len({item.status for item in values}) != len(values):
            raise ValueError("Status entries must not be duplicated")
        return values


class StatsLive(StatsModel):
    as_of: UTCDateTime
    scope: StatsScope
    available: StatsCount
    active: StatsCount
    paused: StatsCount
    banned: StatsCount
    total: StatsCount
    other: StatsCount

    @model_validator(mode="after")
    def validate_total(self) -> Self:
        counted = (
            self.available
            + self.active
            + self.paused
            + self.banned
            + self.other
        )
        if self.total != counted:
            raise ValueError("Account categories must sum to the total")
        return self
