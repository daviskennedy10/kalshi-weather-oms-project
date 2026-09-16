from collections.abc import AsyncIterator
from datetime import date
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from weather_oms.config import Settings
from weather_oms.dashboard.summary import (
    DashboardSummary,
    build_dashboard_summary,
)
from weather_oms.storage.db import Database
from weather_oms.storage.paper_analysis_repository import (
    load_paper_probability_observations,
)
from weather_oms.storage.paper_position_repository import (
    load_paper_positions_for_date,
)
from weather_oms.storage.paper_risk_decision_repository import (
    load_paper_decision_metrics,
    load_paper_decision_timings,
)


async def get_database_session() -> (
    AsyncIterator[AsyncSession]
):
    database = Database(Settings().database_url)

    try:
        async with database.session() as session:
            yield session
    finally:
        await database.close()


DatabaseSession = Annotated[
    AsyncSession,
    Depends(get_database_session),
]


async def get_dashboard_summary(
    target_date: date,
    session: DatabaseSession,
) -> DashboardSummary:
    positions = await load_paper_positions_for_date(
        session=session,
        target_date=target_date,
    )
    timings = await load_paper_decision_timings(
        session=session,
        target_date=target_date,
    )
    decision_metrics = await load_paper_decision_metrics(
        session=session,
        target_date=target_date,
    )
    observations = (
        await load_paper_probability_observations(
            session=session,
            target_date=target_date,
        )
    )

    return build_dashboard_summary(
        positions=positions,
        stored_timings=timings,
        observations=observations,
        decision_metrics=decision_metrics,
    )