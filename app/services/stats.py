"""Read-only statistics over retained domain rows and audit events."""

from calendar import monthrange
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import TypeAdapter
from sqlalchemy import BigInteger, DateTime, Integer, bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import TextualSelect

from app.core.settings.app_settings import (
    StatsCoverageName, StatsCoverageStarts,
)
from app.core.utc import UTCDateTime
from app.crud.user import user as user_crud
from app.models.user import User
from app.schemas.stats import (
    StatsComparison,
    StatsCoverage,
    StatsCoverageGroup,
    StatsCoverageState,
    StatsDelivery,
    StatsLive,
    StatsLiveQuery,
    StatsMessageCohort,
    StatsMessageStatus,
    StatsMessageStatusName,
    StatsMetrics,
    StatsPeriod,
    StatsScope,
    StatsSessionStatus,
    StatsSummary,
    StatsSummaryQuery,
    StatsTrendPoint,
)


_UTC_DATETIME = TypeAdapter(UTCDateTime)
_COVERAGE_STARTS = TypeAdapter(StatsCoverageStarts)
_METRIC_GROUPS: dict[StatsCoverageName, tuple[str, ...]] = {
    "lifecycle": (
        "opened", "finished", "session_bans", "account_bans", "auto_finished",
    ),
    "message_events": ("sent", "delivered", "undelivered", "failed"),
    "account_errors": ("account_errors",),
    "session_errors": ("session_errors",),
}
_MESSAGE_STATUSES: tuple[StatsMessageStatusName, ...] = (
    "sent", "delivered", "undelivered", "failed",
)


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
        account_scope = "WHERE a.user_id = :scope_user_id" if scoped else ""
        error_scope = "AND l.user_id = :scope_user_id" if scoped else ""
        sql = """
WITH
p AS (
    SELECT CAST(:start_at AS timestamptz) AS start_at,
           CAST(:effective_end_at AS timestamptz) AS end_at
),
cfg AS (
    SELECT p.*,
           CASE WHEN end_at - start_at <= INTERVAL '24 hours'
                THEN 'hour' ELSE 'day' END AS unit,
           CASE WHEN end_at - start_at <= INTERVAL '24 hours'
                THEN INTERVAL '1 hour' ELSE INTERVAL '1 day' END AS step
    FROM p
),
periods AS (
    SELECT 'current'::text AS period, start_at, end_at FROM p
    UNION ALL
    SELECT 'previous',
           ((start_at AT TIME ZONE 'UTC') - (end_at - start_at))
               AT TIME ZONE 'UTC',
           start_at FROM p
),
bounds AS (
    SELECT MIN(start_at) AS lo, MAX(end_at) AS hi FROM periods
),
owned_accounts AS NOT MATERIALIZED (
    SELECT a.id FROM account a {account_scope}
),
owned_sessions AS NOT MATERIALIZED (
    SELECT s.id FROM session s
    JOIN owned_accounts a ON a.id = s.account_id
),
owned_messages AS NOT MATERIALIZED (
    SELECT m.id, m.created_at, m.status FROM message m
    JOIN owned_sessions s ON s.id = m.session_id
),
window_log AS NOT MATERIALIZED (
    SELECT l.* FROM log l CROSS JOIN bounds b
    WHERE l.created_at >= b.lo AND l.created_at < b.hi
),
session_facts AS (
    SELECT l.created_at AS at, v.metric
    FROM window_log l
    JOIN owned_sessions s ON s.id = l.session_id
    CROSS JOIN LATERAL (VALUES
        ('opened', l.event = 'session.create' AND l.status = 'active'),
        ('finished', l.event = 'session.status' AND l.status = 'finished'),
        ('session_bans', l.event = 'session.status' AND l.status = 'banned'),
        ('auto_finished', l.event = 'session.status' AND l.status = 'finished'
            AND l.source = 'scheduler')
    ) AS v(metric, include_event)
    WHERE l.event IN ('session.create', 'session.status') AND v.include_event
),
account_facts AS (
    SELECT l.created_at AS at, 'account_bans'::text AS metric
    FROM window_log l JOIN owned_accounts a ON a.id = l.account_id
    WHERE l.event = 'account.status' AND l.status = 'banned'
),
message_candidates AS (
    SELECT DISTINCT l.message_id
    FROM window_log l JOIN owned_messages m ON m.id = l.message_id
    WHERE l.event IN ('message.create', 'message.status')
      AND l.status IN ('sent', 'delivered', 'undelivered', 'failed')
),
message_first AS (
    SELECT c.message_id, f.*
    FROM message_candidates c CROSS JOIN bounds b
    CROSS JOIN LATERAL (
        SELECT MIN(l.created_at) FILTER (
                   WHERE l.status IN ('sent', 'delivered', 'undelivered')
               ) AS sent_at,
               MIN(l.created_at) FILTER (
                   WHERE l.status = 'delivered') AS delivered_at,
               MIN(l.created_at) FILTER (
                   WHERE l.status = 'undelivered') AS undelivered_at,
               MIN(l.created_at) FILTER (
                   WHERE l.status = 'failed') AS failed_at
        FROM log l
        WHERE l.message_id = c.message_id
          AND l.event IN ('message.create', 'message.status')
          AND l.status IN ('sent', 'delivered', 'undelivered', 'failed')
          AND l.created_at < b.hi
    ) f
),
message_facts AS (
    SELECT v.at, v.metric
    FROM message_first f CROSS JOIN bounds b
    CROSS JOIN LATERAL (VALUES
        ('sent', f.sent_at), ('delivered', f.delivered_at),
        ('undelivered', f.undelivered_at), ('failed', f.failed_at)
    ) v(metric, at)
    WHERE v.at >= b.lo AND v.at < b.hi
),
creation_facts AS (
    SELECT m.created_at AS at, 'message_created'::text AS metric
    FROM owned_messages m CROSS JOIN bounds b
    WHERE m.created_at >= b.lo AND m.created_at < b.hi
),
error_candidates AS (
    SELECT DISTINCT l.event, l.user_id,
           NULLIF(l.context ->> 'operation_id', '') AS operation_id
    FROM window_log l
    WHERE l.event IN ('account.error', 'session.error')
      AND l.source = 'ext_api' {error_scope}
      AND NULLIF(l.context ->> 'operation_id', '') IS NOT NULL
),
error_first AS (
    SELECT c.event, c.user_id, c.operation_id, MIN(l.created_at) AS at
    FROM error_candidates c
    JOIN log l ON l.event = c.event
      AND l.user_id IS NOT DISTINCT FROM c.user_id
      AND NULLIF(l.context ->> 'operation_id', '') = c.operation_id
    CROSS JOIN bounds b
    WHERE l.source = 'ext_api'
      AND l.event IN ('account.error', 'session.error') {error_scope}
      AND l.created_at < b.hi
    GROUP BY c.event, c.user_id, c.operation_id
),
error_facts AS (
    SELECT f.at,
           CASE f.event WHEN 'account.error' THEN 'account_errors'
                        ELSE 'session_errors' END AS metric
    FROM error_first f CROSS JOIN bounds b
    WHERE f.at >= b.lo AND f.at < b.hi
),
facts AS (
    SELECT * FROM session_facts UNION ALL
    SELECT * FROM account_facts UNION ALL
    SELECT * FROM message_facts UNION ALL
    SELECT * FROM creation_facts UNION ALL
    SELECT * FROM error_facts
),
aggregated AS (
    SELECT r.period,
           date_trunc(c.unit, f.at AT TIME ZONE 'UTC') AS bucket,
           f.metric, COUNT(*) AS value
    FROM facts f JOIN periods r ON f.at >= r.start_at AND f.at < r.end_at
    CROSS JOIN cfg c
    GROUP BY r.period, date_trunc(c.unit, f.at AT TIME ZONE 'UTC'), f.metric
),
metric_names(metric) AS (
    VALUES ('opened'), ('finished'), ('session_bans'), ('account_bans'),
           ('sent'), ('delivered'), ('undelivered'), ('failed'),
           ('account_errors'), ('session_errors'), ('auto_finished'),
           ('message_created')
),
buckets AS (
    SELECT r.period, g.bucket,
           GREATEST(g.bucket AT TIME ZONE 'UTC', r.start_at) AS from_at,
           LEAST((g.bucket + c.step) AT TIME ZONE 'UTC', r.end_at) AS to_at
    FROM periods r CROSS JOIN cfg c
    CROSS JOIN LATERAL generate_series(
        date_trunc(c.unit, r.start_at AT TIME ZONE 'UTC'),
        r.end_at AT TIME ZONE 'UTC', c.step
    ) AS g(bucket)
    WHERE r.start_at < r.end_at AND g.bucket < r.end_at AT TIME ZONE 'UTC'
),
counters AS (
    SELECT b.period, b.bucket AT TIME ZONE 'UTC' AS key,
           b.from_at, b.to_at, n.metric, COALESCE(a.value, 0) AS value
    FROM buckets b CROSS JOIN metric_names n
    LEFT JOIN aggregated a
      ON a.period = b.period AND a.bucket = b.bucket AND a.metric = n.metric
),
message_cohort AS (
    SELECT COUNT(*) AS total,
           COUNT(*) FILTER (WHERE m.status = 0) AS created,
           COUNT(*) FILTER (WHERE m.status = -1) AS waiting,
           COUNT(*) FILTER (WHERE m.status = 1) AS sent,
           COUNT(*) FILTER (WHERE m.status = 2) AS delivered,
           COUNT(*) FILTER (WHERE m.status = 3) AS undelivered,
           COUNT(*) FILTER (WHERE m.status = 4) AS failed,
           COUNT(*) FILTER (
               WHERE m.status IS NULL
                  OR m.status NOT IN (-1, 0, 1, 2, 3, 4)) AS unknown_status
    FROM owned_messages m CROSS JOIN p
    WHERE m.created_at >= p.start_at AND m.created_at < p.end_at
),
gap_counts AS (
    SELECT r.period,
           CASE l.event WHEN 'account.error' THEN 'account_errors'
                        ELSE 'session_errors' END AS metric_group,
           COUNT(*) AS invalid_rows
    FROM window_log l
    JOIN periods r ON l.created_at >= r.start_at AND l.created_at < r.end_at
    WHERE l.event IN ('account.error', 'session.error')
      AND l.source = 'ext_api' {error_scope}
      AND NULLIF(l.context ->> 'operation_id', '') IS NULL
    GROUP BY r.period, l.event
)
SELECT statement_timestamp() AS generated_at,
       COALESCE((SELECT jsonb_agg(to_jsonb(c)
                    ORDER BY c.period, c.key, c.metric)
                 FROM counters c), '[]'::jsonb) AS counters,
       (SELECT to_jsonb(m) FROM message_cohort m) AS message_cohort,
       COALESCE((SELECT jsonb_agg(to_jsonb(g)) FROM gap_counts g),
                '[]'::jsonb) AS audit_gaps
""".format(account_scope=account_scope, error_scope=error_scope)
        statement = text(sql).bindparams(
            bindparam("start_at", type_=DateTime(timezone=True)),
            bindparam("effective_end_at", type_=DateTime(timezone=True)),
        )
        if scoped:
            statement = statement.bindparams(
                bindparam("scope_user_id", type_=Integer()),
            )
        return statement.columns(
            generated_at=DateTime(timezone=True), counters=JSONB(),
            message_cohort=JSONB(), audit_gaps=JSONB(),
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
        start: datetime, end: datetime, since: datetime | None, gap: bool,
    ) -> tuple[StatsCoverageState, str | None]:
        if since is None:
            return "unavailable", "collection_start_unknown"
        if end <= since:
            return "unavailable", "before_collection_start"
        if gap:
            return "partial", "missing_operation_id"
        if start < since:
            return "partial", "period_crosses_collection_start"
        return "recorded", None

    @classmethod
    def _mask_metrics(
        cls, values: Mapping[str, Any], start: datetime, end: datetime,
        starts: StatsCoverageStarts, gaps: set[str],
    ) -> StatsMetrics:
        masked = dict(values)
        if start < end:
            for group, fields in _METRIC_GROUPS.items():
                state, _ = cls._coverage_state(
                    start, end, starts.get(group), group in gaps,
                )
                if state != "recorded":
                    masked.update(dict.fromkeys(fields, None))
        return StatsMetrics.model_validate(masked)

    @classmethod
    def _build_summary(
        cls, result: Mapping[Any, Any], period: StatsPeriod, scope: StatsScope,
        starts: StatsCoverageStarts,
    ) -> StatsSummary:
        raw_totals = {
            name: dict.fromkeys(StatsMetrics.model_fields, 0)
            for name in ("current", "previous")
        }
        points: dict[datetime, dict[str, Any]] = {}
        for row in result["counters"]:
            raw_totals[row["period"]][row["metric"]] += row["value"]
            if row["period"] == "current":
                key = _UTC_DATETIME.validate_python(row["key"])
                point = points.setdefault(key, {
                    "key": key,
                    "from_at": _UTC_DATETIME.validate_python(row["from_at"]),
                    "to_at": _UTC_DATETIME.validate_python(row["to_at"]),
                })
                point[row["metric"]] = row["value"]
        gaps: dict[str, set[str]] = {"current": set(), "previous": set()}
        for gap in result["audit_gaps"]:
            if gap["invalid_rows"]:
                gaps[gap["period"]].add(gap["metric_group"])

        ranges = {
            "current": (period.start_at, period.effective_end_at),
            "previous": (
                period.comparison.start_at, period.comparison.end_at,
            ),
        }
        totals = {
            name: cls._mask_metrics(values, *ranges[name], starts, gaps[name])
            for name, values in raw_totals.items()
        }
        trend = []
        for key in sorted(points):
            point = points[key]
            values = {name: point[name] for name in StatsMetrics.model_fields}
            masked = cls._mask_metrics(
                values, point["from_at"], point["to_at"],
                starts, gaps["current"],
            )
            trend.append(StatsTrendPoint(
                **masked.model_dump(), key=key,
                from_at=point["from_at"], to_at=point["to_at"],
            ))

        coverage = {}
        for group in _METRIC_GROUPS:
            current, current_reason = cls._coverage_state(
                *ranges["current"], starts.get(group),
                group in gaps["current"],
            )
            previous, previous_reason = cls._coverage_state(
                *ranges["previous"], starts.get(group),
                group in gaps["previous"],
            )
            coverage[group] = StatsCoverageGroup.model_validate({
                "from": starts.get(group), "current_state": current,
                "previous_state": previous, "current_reason": current_reason,
                "previous_reason": previous_reason,
            })
        cohort = result["message_cohort"]
        terminal = (
            cohort["delivered"] + cohort["undelivered"] + cohort["failed"]
        )
        return StatsSummary(
            **period.model_dump(), generated_at=result["generated_at"],
            scope=scope, totals=totals["current"], previous=totals["previous"],
            trend=trend,
            statuses=[
                StatsMessageStatus(status=name, value=cohort[name])
                for name in _MESSAGE_STATUSES
            ],
            message_cohort=StatsMessageCohort(**{
                name: cohort[name] for name in StatsMessageCohort.model_fields
            }),
            session_statuses=[
                StatsSessionStatus(
                    status="opened", value=totals["current"].opened,
                ),
                StatsSessionStatus(
                    status="finished", value=totals["current"].finished,
                ),
                StatsSessionStatus(
                    status="banned", value=totals["current"].session_bans,
                ),
            ],
            delivery=StatsDelivery(
                delivered=cohort["delivered"], terminal=terminal,
                rate=round(cohort["delivered"] / terminal * 100, 2)
                if terminal else None,
            ),
            coverage=StatsCoverage.model_validate(coverage),
        )

    async def get_summary(
        self, db: AsyncSession, *, current_user: User,
        query: StatsSummaryQuery,
        coverage_starts: StatsCoverageStarts | None = None,
        now: datetime | None = None,
    ) -> StatsSummary:
        """Read both periods and the cohort in one database snapshot."""
        period = self.resolve_period(query, now=now)
        scope = await self.resolve_scope(
            db, current_user=current_user, query=query,
        )
        starts = _COVERAGE_STARTS.validate_python(
            {} if coverage_starts is None else coverage_starts,
        )
        scoped = scope.user_id is not None
        params: dict[str, Any] = {
            "start_at": period.start_at,
            "effective_end_at": period.effective_end_at,
        }
        if scoped:
            params["scope_user_id"] = scope.user_id
        result = await db.execute(
            self._summary_statement(scoped=scoped), params,
        )
        return self._build_summary(
            result.mappings().one(), period, scope, starts,
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
