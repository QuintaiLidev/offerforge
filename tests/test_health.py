from __future__ import annotations

import httpx
import pytest

from app.main import app


@pytest.mark.anyio
async def test_health_endpoint_returns_expected_payload() -> None:
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "OfferForge"}
