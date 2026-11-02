from fastapi.testclient import TestClient

from app.main import app


def test_health_and_openapi_are_available() -> None:
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok", "service": "AgentFlow"}
    assert client.get("/openapi.json").status_code == 200


def test_execution_request_validates_user_request() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/executions", json={"user_request": ""})
    assert response.status_code == 422
