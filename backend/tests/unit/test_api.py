"""Focused API integration tests for WEAVE."""

import pytest
from fastapi.testclient import TestClient

from weave_brain.api.main import create_app
from weave_brain.core.config import Settings
from weave_brain.domain.models import ChatResponse
from weave_brain.services.graph_service import bounded_view

AUTH = "service:authentication-api"


@pytest.fixture
def client():
    app = create_app(Settings(_env_file=None, development_fixtures=True))
    return TestClient(app, raise_server_exceptions=False)


def test_live_endpoint(client):
    response = client.get("/api/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_fixture_mode_readiness_returns_503(client):
    response = client.get("/api/health")
    assert response.status_code == 503
    assert response.json() == {"status": "development", "database": "fixtures"}


def test_chat_success(client):
    response = client.post(
        "/api/chat", json={"question": "Who owns authentication-api?"}
    )
    assert response.status_code == 200, response.text
    result = ChatResponse.model_validate(response.json())
    assert result.answer and result.message_id
    assert any("fixture" in w.lower() for w in result.warnings)


def test_chat_validation_empty_and_oversized(client):
    assert client.post("/api/chat", json={"question": "   "}).status_code == 400
    assert client.post("/api/chat", json={"question": "x" * 4001}).status_code == 400
    assert (
        client.post(
            "/api/chat",
            json={"question": "Valid question", "conversation_id": "   "},
        ).status_code
        == 400
    )


def test_overview_direction_and_shape(client):
    response = client.get(f"/api/services/{AUTH}")
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["team"]["id"] == "team:platform-engineering"
    assert any(
        e["source_id"] == "team:platform-engineering"
        and e["target_id"] == AUTH
        and e["relationship_type"] == "OWNS"
        for e in result["graph"]["edges"]
    )


def test_blast_radius(client):
    response = client.get(f"/api/services/{AUTH}/blast-radius")
    assert response.status_code == 200, response.text
    result = response.json()
    assert {n["id"] for n in result["affected_services"]} == {
        "service:user-profile-api",
        "service:notification-service",
    }
    assert all(e["target_id"] == AUTH for e in result["graph"]["edges"])


@pytest.mark.parametrize(
    "path",
    [
        f"/api/graph/neighborhood/{AUTH}?depth=0",
        f"/api/graph/neighborhood/{AUTH}?depth=4",
        f"/api/services/{AUTH}/blast-radius?max_depth=4",
        "/api/search?q=%20",
        "/api/search",
        "/api/entities/not-an-id",
        "/api/graph/shortest-path?from_id=bad&to_id=bad",
    ],
)
def test_query_validation(client, path):
    assert client.get(path).status_code == 400


@pytest.mark.parametrize(
    "path",
    [
        "/api/entities/service:unknown",
        "/api/services/service:unknown",
        "/api/graph/neighborhood/service:unknown",
    ],
)
def test_unknown_entity_returns_404(client, path):
    assert client.get(path).status_code == 404


@pytest.mark.parametrize(
    "id_path", ["repository:acme/auth-api", "repository%3Aacme%2Fauth-api"]
)
def test_slash_ids(client, id_path):
    response = client.get(f"/api/entities/{id_path}")
    assert response.status_code == 200
    assert response.json()["id"] == "repository:acme/auth-api"


def test_shortest_preserves_direction(client):
    response = client.get(
        "/api/graph/shortest-path",
        params={"from_id": AUTH, "to_id": "team:platform-engineering"},
    )
    assert response.status_code == 200
    result = response.json()
    assert result["path_found"]
    assert result["graph"]["edges"][0]["source_id"] == "team:platform-engineering"
    assert len(result["graph"]["edges"]) <= 3


def test_canonical_reports_router_registered(client):
    health_resp = client.get("/api/v1/reports/health-score")
    assert health_resp.status_code in (200, 503)

    gaps_resp = client.get("/api/v1/reports/knowledge-gaps")
    assert gaps_resp.status_code in (200, 503)

    onboard_resp = client.get(f"/api/v1/reports/onboarding?service_id={AUTH}")
    assert onboard_resp.status_code in (200, 500, 503)


def test_database_error_and_recovery(monkeypatch):
    app = create_app(Settings(_env_file=None, development_fixtures=False))
    client = TestClient(app, raise_server_exceptions=False)

    def broken(_query):
        raise ConnectionError("password=do-not-expose")

    monkeypatch.setattr(app.state.graph_service, "search", broken)
    failed = client.get("/api/health")
    assert failed.status_code == 503 and "do-not-expose" not in failed.text
    assert client.get("/api/live").status_code == 200
    monkeypatch.setattr(app.state.graph_service, "search", lambda _: [])
    assert client.get("/api/health").json() == {"status": "ok", "database": "connected"}


def test_unexpected_errors_are_sanitized(monkeypatch, caplog):
    app = create_app(Settings(_env_file=None))

    def broken(_query):
        raise RuntimeError("credential=never-log-this")

    monkeypatch.setattr(app.state.graph_service, "search", broken)
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/api/search?q=auth", headers={"Origin": "http://localhost:5173"}
    )
    assert response.status_code == 500
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "never-log-this" not in response.text + caplog.text


@pytest.mark.parametrize(
    "origins",
    [
        '["https://example.com", "http://localhost:5173"]',
        "https://example.com, http://localhost:5173",
    ],
)
def test_cors_parsing(origins):
    settings = Settings(_env_file=None, allowed_origins=origins)
    assert settings.origins == ["https://example.com", "http://localhost:5173"]
    client = TestClient(create_app(settings))
    response = client.options(
        "/api/chat",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers["access-control-allow-origin"] == "https://example.com"
    denied = client.options(
        "/api/chat",
        headers={
            "Origin": "https://other.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert "access-control-allow-origin" not in denied.headers


def test_shortest_path_never_exceeds_three_hops(client, monkeypatch):
    app = client.app
    nodes = [
        {"id": f"service:n-{i}", "type": "service", "title": str(i)} for i in range(5)
    ]
    edges = [
        {
            "source_id": f"service:n-{i}",
            "target_id": f"service:n-{i + 1}",
            "relationship_type": "DEPENDS_ON",
        }
        for i in range(4)
    ]
    monkeypatch.setattr(
        app.state.graph_service,
        "neighborhood",
        lambda *_: bounded_view({"nodes": nodes, "edges": edges}),
    )
    result = client.get(
        "/api/graph/shortest-path?from_id=service:n-0&to_id=service:n-4"
    )
    assert not result.json()["path_found"]
