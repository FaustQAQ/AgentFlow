import httpx
import pytest

from app.main import app

@pytest.mark.asyncio
async def test_health_and_openapi_are_available() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).json() == {"status": "ok", "service": "AgentFlow - Agentic Sales Analytics Platform"}
        assert (await client.get("/openapi.json")).status_code == 200

@pytest.mark.asyncio
async def test_execution_request_validates_user_request() -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/executions", json={"user_request": ""})
        assert response.status_code == 422
