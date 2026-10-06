"""Read-only statistics over retained domain rows and audit events."""

from calendar import monthrange
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import BigInteger, DateTime, Integer, String, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import TextualSelect

from app.core.utc import UTCDateTime
from app.crud.user import user as user_crud
from app.models.user import User
from app.schemas.stats import (
    StatsComparison,
    StatsCoverage,
    StatsCoverageGroup,
    StatsCoverageState,
    StatsLive,
    StatsLiveQuery,
    StatsMetrics,
    StatsPeriod,
    StatsScope,
    StatsSummary,
    StatsSummaryQuery,
    StatsTrendPoint,
)


_UTC_DATETIME = TypeAdapter(UTCDateTime)
_COVERAGE_GROUPS = (
    "lifecycle", "message_events", "account_errors", "session_errors",
)
_ERROR_GROUPS = ("account_errors", "session_errors")


class StatsPeriodError(ValueError):
    """The requested reporting period is invalid (HTTP 422 at the API
    boundary).
    """


class StatsScopeDeniedError(PermissionError):
    """An ordinary user requested another user's scope (HTTP 403)."""


class StatsUserNotFoundError(LookupError):
    """An administrator selected a nonexistent user (HTTP 404)."""


def _next_month(value: datetime) -> datetime:
    year = value.year + (value.month == 12)
    month = value.month % 12 + 1
    if year > datetime.max.year:
        return datetime.max.replace(tzinfo=UTC)
    day = min(value.day, monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)


def _user_scope(owner: User) -> StatsScope:
    return StatsScope(
        user_id=owner.id,
        mode="user",
        label=owner.name or owner.login or f"Пользователь {owner.id}",
    )


class StatsService:
    @staticmethod
    def _summary_statement(*, scoped: bool) -> TextualSelect:
        # Only fixed predicates vary; request values remain bind parameters.
        log_scope = "AND l.user_id = :scope_user_id" if scoped else ""
        sql = """
WITH
lifecycle_buckets AS MATERIALIZED (
    SELECT CASE WHEN l.created_at >= :start_at
                THEN 'current' ELSE 'previous' END AS period,
           date_trunc(:granularity, l.created_at AT TIME ZONE 'UTC')
               AT TIME ZONE 'UTC' AS key,
           COUNT(*) FILTER (WHERE l.event = 'session.create'
                            AND l.status = 'active') AS opened,
           COUNT(*) FILTER (WHERE l.event = 'session.status'
                            AND l.status = 'finished') AS finished,
           COUNT(*) FILTER (WHERE l.event = 'session.status'
                            AND l.status = 'banned') AS session_bans,
           COUNT(*) FILTER (WHERE l.event = 'account.status'
                            AND l.status = 'banned') AS account_bans,
           COUNT(*) FILTER (WHERE l.event = 'session.status'
                            AND l.status = 'finished'
                            AND l.source = 'scheduler') AS auto_finished
    FROM log l
    WHERE l.created_at >= :previous_start
      AND l.created_at < :effective_end_at {log_scope}
      AND (
          (l.session_id IS NOT NULL AND (
              (l.event = 'session.create' AND l.status = 'active')
              OR (l.event = 'session.status'
                  AND l.status IN ('finished', 'banned'))
          ))
          OR (l.account_id IS NOT NULL
              AND l.event = 'account.status' AND l.status = 'banned')
      )
    GROUP BY 1, 2
),
message_first AS MATERIALIZED (
    SELECT l.message_id,
           MIN(l.created_at) FILTER (
               WHERE l.status IN ('sent', 'delivered', 'undelivered')
           ) AS sent_at,
           MIN(l.created_at) FILTER (
               WHERE l.status = 'delivered') AS delivered_at,
           MIN(l.created_at) FILTER (
               WHERE l.status = 'undelivered') AS undelivered_at,
           MIN(l.created_at) FILTER (
               WHERE l.status = 'failed') AS failed_at
    FROM log l
    WHERE l.message_id IS NOT NULL
      AND l.event IN ('message.create', 'message.status')
      AND l.status IN ('sent', 'delivered', 'undelivered', 'failed')
      AND l.created_at < :effective_end_at {log_scope}
      AND :previous_start < :effective_end_at
    GROUP BY l.message_id
),
message_facts AS (
    SELECT sent_at AS at, 'sent'::text AS metric FROM message_first
    UNION ALL
    SELECT delivered_at, 'delivered' FROM message_first
    UNION ALL
    SELECT undelivered_at, 'undelivered' FROM message_first
    UNION ALL
    SELECT failed_at, 'failed' FROM message_first
),
error_first AS (
    SELECT l.event, l.user_id,
           NULLIF(l.context ->> 'operation_id', '') AS operation_id,
           MIN(l.created_at) AS at
    FROM log l
    WHERE l.source = 'ext_api'
      AND l.event IN ('account.error', 'session.error')
      AND NULLIF(l.context ->> 'operation_id', '') IS NOT NULL
      AND l.created_at < :effective_end_at {log_scope}
      AND :previous_start < :effective_end_at
    GROUP BY l.event, l.user_id, NULLIF(l.context ->> 'operation_id', '')
),
error_facts AS (
    SELECT f.at,
           CASE f.event WHEN 'account.error' THEN 'account_errors'
                         ELSE 'session_errors' END AS metric
    FROM error_first f
),
facts AS (
    SELECT * FROM message_facts UNION ALL
    SELECT * FROM error_facts
),
event_buckets AS (
    SELECT CASE WHEN f.at >= :start_at
                THEN 'current' ELSE 'previous' END AS period,
           date_trunc(:granularity, f.at AT TIME ZONE 'UTC')
               AT TIME ZONE 'UTC' AS key,
           f.metric, COUNT(*) AS value
    FROM facts f
    WHERE f.at >= :previous_start AND f.at < :effective_end_at
    GROUP BY 1, 2, 3
),
counters AS (
    SELECT period, key, 'opened'::text AS metric, opened AS value
    FROM lifecycle_buckets WHERE opened > 0
    UNION ALL
    SELECT period, key, 'finished', finished
    FROM lifecycle_buckets WHERE finished > 0
    UNION ALL
    SELECT period, key, 'session_bans', session_bans
    FROM lifecycle_buckets WHERE session_bans > 0
    UNION ALL
    SELECT period, key, 'account_bans', account_bans
    FROM lifecycle_buckets WHERE account_bans > 0
    UNION ALL
    SELECT period, key, 'auto_finished', auto_finished
    FROM lifecycle_buckets WHERE auto_finished > 0
    UNION ALL
    SELECT period, key, metric, value FROM event_buckets
),
gap_counts AS (
    SELECT CASE WHEN l.created_at >= :start_at
                THEN 'current' ELSE 'previous' END AS period,
           CASE l.event WHEN 'account.error' THEN 'account_errors'
                         ELSE 'session_errors' END AS metric_group,
           COUNT(*) AS invalid_rows
    FROM log l
    WHERE l.event IN ('account.error', 'session.error')
      AND l.source = 'ext_api' {log_scope}
      AND NULLIF(l.context ->> 'operation_id', '') IS NULL
      AND l.created_at >= :previous_start
      AND l.created_at < :effective_end_at
    GROUP BY 1, l.event
)
SELECT statement_timestamp() AS generated_at,
       COALESCE((SELECT jsonb_agg(to_jsonb(c)
                     ORDER BY c.period, c.key, c.metric)
                  FROM counters c), '[]'::jsonb) AS counters,
       COALESCE((SELECT jsonb_agg(to_jsonb(g)) FROM gap_counts g),
                 '[]'::jsonb) AS audit_gaps
""".format(log_scope=log_scope)
        statement = text(sql).bindparams(
            bindparam("start_at", type_=DateTime(timezone=True)),
            bindparam("previous_start", type_=DateTime(timezone=True)),
            bindparam("effective_end_at", type_=DateTime(timezone=True)),
            bindparam("granularity", type_=String()),
        )
        if scoped:
            statement = statement.bindparams(
                bindparam("scope_user_id", type_=Integer()),
            )
        return statement.columns(
            generated_at=DateTime(timezone=True), counters=JSONB(),
            audit_gaps=JSONB(),
        )

    @staticmethod
    def _live_statement(*, scoped: bool) -> TextualSelect:
        account_scope = "WHERE a.user_id = :scope_user_id" if scoped else ""
        statement = text("""
WITH p AS (
    SELECT statement_timestamp() AS as_of
),
scoped AS (
    SELECT a.status,
           (a.file_name IS NOT NULL OR a.hash IS NOT NULL) AS has_payload,
           (a.updated_at IS NULL OR a.cooldown IS NULL
            OR a.updated_at + make_interval(mins => a.cooldown) < p.as_of
           ) AS cooldown_elapsed
    FROM account a CROSS JOIN p
    {account_scope}
),
counts AS (
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE status = 0 AND has_payload
                            AND cooldown_elapsed) AS available,
           COUNT(*) FILTER (WHERE status = 1) AS active,
           COUNT(*) FILTER (WHERE status = 0
                            AND NOT cooldown_elapsed) AS paused,
           COUNT(*) FILTER (WHERE status = -1) AS banned
    FROM scoped
)
SELECT p.as_of, c.*,
       c.total - c.available - c.active - c.paused - c.banned AS other
FROM counts c CROSS JOIN p
""".format(account_scope=account_scope))
        if scoped:
            statement = statement.bindparams(
                bindparam("scope_user_id", type_=Integer()),
            )
        return statement.columns(
            as_of=DateTime(timezone=True), total=BigInteger(),
            available=BigInteger(), active=BigInteger(), paused=BigInteger(),
            banned=BigInteger(), other=BigInteger(),
        )

    @staticmethod
    def _coverage_state(
        gap: bool,
    ) -> tuple[StatsCoverageState, str | None]:
        if gap:
            return "partial", "missing_operation_id"
        return "recorded", None

    @staticmethod
    def _mask_error_gaps(
        values: Mapping[str, Any], gaps: set[str],
    ) -> StatsMetrics:
        # Identifiable operations are only a subtotal when the period has a
        # gap. Mask that error group in every bucket of the affected period.
        masked = dict(values)
        for group in _ERROR_GROUPS:
            if group in gaps:
                masked[group] = None
        return StatsMetrics.model_validate(masked)

    @classmethod
    def _build_summary(
        cls, result: Mapping[Any, Any], period: StatsPeriod, scope: StatsScope,
    ) -> StatsSummary:
        raw_totals = {
            name: dict.fromkeys(StatsMetrics.model_fields, 0)
            for name in ("current", "previous")
        }
        points: dict[datetime, dict[str, Any]] = {}
        if period.start_at < period.effective_end_at:
            key = period.start_at.replace(minute=0, second=0, microsecond=0)
            step = timedelta(hours=1)
            if period.granularity == "day":
                key = key.replace(hour=0)
                step = timedelta(days=1)
            while key < period.effective_end_at:
                to_at = key + min(step, period.effective_end_at - key)
                points[key] = {
                    **dict.fromkeys(StatsMetrics.model_fields, 0),
                    "key": key,
                    "from_at": max(key, period.start_at),
                    "to_at": to_at,
                }
                key = to_at
        for row in result["counters"]:
            raw_totals[row["period"]][row["metric"]] += row["value"]
            if row["period"] == "current":
                key = _UTC_DATETIME.validate_python(row["key"])
                points[key][row["metric"]] += row["value"]
        gaps: dict[str, set[str]] = {"current": set(), "previous": set()}
        for gap in result["audit_gaps"]:
            if gap["invalid_rows"]:
                gaps[gap["period"]].add(gap["metric_group"])

        totals = {
            name: cls._mask_error_gaps(values, gaps[name])
            for name, values in raw_totals.items()
        }
        trend = []
        for key in sorted(points):
            point = points[key]
            values = {name: point[name] for name in StatsMetrics.model_fields}
            masked = cls._mask_error_gaps(values, gaps["current"])
            trend.append(StatsTrendPoint(
                **masked.model_dump(), key=key,
                from_at=point["from_at"], to_at=point["to_at"],
            ))

        coverage = {}
        for group in _COVERAGE_GROUPS:
            current, current_reason = cls._coverage_state(
                group in gaps["current"],
            )
            previous, previous_reason = cls._coverage_state(
                group in gaps["previous"],
            )
            coverage[group] = StatsCoverageGroup.model_validate({
                "from": None, "current_state": current,
                "previous_state": previous, "current_reason": current_reason,
                "previous_reason": previous_reason,
            })
        return StatsSummary(
            **period.model_dump(), generated_at=result["generated_at"],
            scope=scope, totals=totals["current"], previous=totals["previous"],
            trend=trend,
            coverage=StatsCoverage.model_validate(coverage),
        )

    async def get_summary(
        self, db: AsyncSession, *, current_user: User,
        query: StatsSummaryQuery,
        now: datetime | None = None,
    ) -> StatsSummary:
        """Count log events in one snapshot, scoped by their recorded user.

        Recorded counts do not establish complete collection or a start date.
        First confirmations are computed within that scope's retained history.
        Error groups with missing operation IDs remain partial and nullable.
        """
        period = self.resolve_period(query, now=now)
        scope = await self.resolve_scope(
            db, current_user=current_user, query=query,
        )
        scoped = scope.user_id is not None
        params: dict[str, Any] = {
            "start_at": period.start_at,
            "previous_start": period.comparison.start_at,
            "effective_end_at": period.effective_end_at,
            "granularity": period.granularity,
        }
        if scoped:
            params["scope_user_id"] = scope.user_id
        result = await db.execute(
            self._summary_statement(scoped=scoped), params,
        )
        return self._build_summary(
            result.mappings().one(), period, scope,
        )

    async def get_live(
        self, db: AsyncSession, *, current_user: User, query: StatsLiveQuery,
    ) -> StatsLive:
        """Read the current account pool independently of reporting dates."""
        scope = await self.resolve_scope(
            db, current_user=current_user, query=query,
        )
        scoped = scope.user_id is not None
        params = {"scope_user_id": scope.user_id} if scoped else {}
        result = await db.execute(self._live_statement(scoped=scoped), params)
        return StatsLive.model_validate({
            **result.mappings().one(), "scope": scope,
        })

    @staticmethod
    def resolve_period(
        query: StatsSummaryQuery, *, now: datetime | None = None,
    ) -> StatsPeriod:
        """Resolve an open end once; compare elapsed durations in UTC."""
        now = datetime.now(UTC) if now is None else now
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError(
                "The statistics clock must have an explicit timezone"
            )
        now = now.astimezone(UTC)
        start = query.start_at
        end = query.end_at if query.end_at is not None else now
        if start > now or end > now:
            raise StatsPeriodError("Reporting dates cannot be in the future")
        if end < start:
            raise StatsPeriodError("The end cannot precede the start")
        if end > _next_month(start):
            raise StatsPeriodError(
                "The period cannot exceed one calendar month"
            )

        duration = end - start
        return StatsPeriod(
            start_at=start,
            end_at=query.end_at,
            effective_end_at=end,
            granularity="hour" if duration <= timedelta(days=1) else "day",
            comparison=StatsComparison(
                start_at=start - duration, end_at=start,
            ),
        )

    @staticmethod
    async def resolve_scope(
        db: AsyncSession, *, current_user: User, query: StatsLiveQuery,
    ) -> StatsScope:
        """Use only the authenticated actor; never look up a forbidden
        user ID.
        """
        requested_id = query.user_id
        if not current_user.is_superuser:
            if requested_id is not None and requested_id != current_user.id:
                raise StatsScopeDeniedError(
                    "Another user's statistics are forbidden"
                )
            return _user_scope(current_user)
        if requested_id is None:
            return StatsScope(
                user_id=None, mode="all", label="Все пользователи",
            )

        owner = await user_crud.get(db, id=requested_id)
        if owner is None:
            raise StatsUserNotFoundError("User not found")
        return _user_scope(owner)


stats_service = StatsService()
