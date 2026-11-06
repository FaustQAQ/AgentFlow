import httpx
import pytest

from app.main import app

@pytest.mark.asyncio
async def test_health_returns_200() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_health_returns_expected_json() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.json() == {"status": "ok", "service": "AgentFlow - Agentic Sales Analytics Platform"}

@pytest.mark.asyncio
async def test_health_returns_json_content_type() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.headers["content-type"].startswith("application/json")
