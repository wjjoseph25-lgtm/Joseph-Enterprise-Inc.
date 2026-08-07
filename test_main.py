from fastapi.testclient import TestClient

from app.main import app


def test_mcp_requires_api_key_by_default(monkeypatch):
    monkeypatch.delenv("MCP_API_KEY", raising=False)
    monkeypatch.delenv("MCP_AUTH_REQUIRED", raising=False)

    response = TestClient(app).post("/mcp")

    assert response.status_code == 503
    assert response.json()["detail"] == "MCP_API_KEY must be set before serving MCP requests"


def test_mcp_rejects_missing_bearer_token(monkeypatch):
    monkeypatch.setenv("MCP_API_KEY", "test-secret")

    response = TestClient(app).post("/mcp")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_mcp_accepts_bearer_token_before_protocol_handling(monkeypatch):
    monkeypatch.setenv("MCP_API_KEY", "test-secret")

    with TestClient(app) as client:
        response = client.post(
            "/mcp",
            headers={"Authorization": "Bearer test-secret"},
        )

    assert response.status_code != 401
    assert response.status_code != 503
