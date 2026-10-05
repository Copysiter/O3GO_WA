"""Authenticated, read-only statistics endpoints."""

import asyncio
import sys
from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app import deps
from app.core.logger import E, logger
from app.core.settings import settings
from app.models import User
from app.schemas.stats import (
    StatsLive, StatsLiveQuery, StatsSummary, StatsSummaryQuery,
)
from app.services.stats import (
    StatsPeriodError, StatsScopeDeniedError, StatsUserNotFoundError,
    stats_service,
)


def _log_database_error(
    action: str, error_type: str, response: HTTPException,
) -> None:
    """Log safe metadata off the event loop, without exception contents."""
    try:
        logger.error(
            event=E.SYSTEM.API.ERROR,
            extra={"action": action, "error": {"type": error_type}},
            exc_info=False,
        )
    except Exception as logger_error:
        response.add_note(
            f"{action} logger failed: {type(logger_error).__name__}"
        )
    # Handlers can swallow stream errors; preserve a second diagnostic path.
    try:
        print(f"{action} failed: {error_type}", file=sys.stderr)
    except Exception as output_error:
        response.add_note(
            f"{action} stderr failed: {type(output_error).__name__}"
        )


class _StatsRoute(APIRoute):
    """Keep the safe database-error boundary around auth dependencies too."""

    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()
        action = f"stats.{self.path.rsplit('/', 1)[-1]}"

        async def handle(request: Request) -> Response:
            try:
                return await original(request)
            except SQLAlchemyError as error:
                response = HTTPException(
                    status_code=503,
                    detail="Statistics are temporarily unavailable",
                )
                await asyncio.to_thread(
                    _log_database_error, action, type(error).__name__,
                    response,
                )
                raise response from None

        return handle


router = APIRouter(route_class=_StatsRoute)


@router.get(
    "/summary", response_model=StatsSummary, response_model_by_alias=True,
)
async def get_summary(
    *,
    query: Annotated[StatsSummaryQuery, Query()],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> StatsSummary:
    """Read a UTC reporting period within the authenticated user's scope.

    Administrators may select any owner or omit user_id for all owners.
    Example: ?start_at=2026-09-01T00:00:00Z&end_at=2026-09-02T00:00:00Z.
    Unknown audit coverage remains null in the response.
    """
    try:
        return await stats_service.get_summary(
            db, current_user=current_user, query=query,
            coverage_starts=settings.STATS_COVERAGE_STARTS,
        )
    except StatsPeriodError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except StatsScopeDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from None
    except StatsUserNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None


@router.get("/live", response_model=StatsLive, response_model_by_alias=True)
async def get_live(
    *,
    query: Annotated[StatsLiveQuery, Query()],
    db: AsyncSession = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> StatsLive:
    """Read the current account pool; reporting dates are not accepted.

    JWT authentication and owner scope match summary. Administrators may
    select an owner with ?user_id=42 or omit it for all owners.
    """
    try:
        return await stats_service.get_live(
            db, current_user=current_user, query=query,
        )
    except StatsScopeDeniedError as error:
        raise HTTPException(status_code=403, detail=str(error)) from None
    except StatsUserNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from None
