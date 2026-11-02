from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_returns_200() -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_health_returns_expected_json() -> None:
    response = client.get("/health")

    assert response.json() == {"status": "ok", "service": "AgentFlow"}


def test_health_returns_json_content_type() -> None:
    response = client.get("/health")

    assert response.headers["content-type"].startswith("application/json")
