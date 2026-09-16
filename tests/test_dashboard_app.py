from datetime import date

import httpx

from weather_oms.dashboard.app import app
from weather_oms.dashboard.dependencies import (
    get_dashboard_summary,
)
from weather_oms.dashboard.summary import (
    DashboardSummary,
    build_dashboard_summary,
)


async def test_health_endpoint() -> None:
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "read-only",
    }


def test_dashboard_exposes_no_write_routes() -> None:
    write_methods = {
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
    }

    exposed_write_routes = [
        route
        for route in app.routes
        if (
            hasattr(route, "methods")
            and route.methods
            and write_methods.intersection(route.methods)
        )
    ]

    assert exposed_write_routes == []

async def test_performance_endpoint() -> None:
    async def fake_summary() -> DashboardSummary:
        return build_dashboard_summary(
            positions=(),
            stored_timings=(),
            observations=(),
            decision_metrics=(),
        )

    app.dependency_overrides[
        get_dashboard_summary
    ] = fake_summary

    try:
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/performance/2026-09-15"
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["target_date"] == str(
        date(2026, 9, 15)
    )
    assert payload["positions"]["total"] == 0
    assert payload["profit"]["total_pnl_dollars"] == "0"
    assert payload["latency"]["samples"] == 0
    assert payload["probability"] is None