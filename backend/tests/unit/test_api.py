"""Offline HTTP contracts and failure recovery; these are not live DB tests."""

import logging

import pytest
from fastapi.testclient import TestClient
from redis.exceptions import ConnectionError

from weave_brain.api.main import create_app
from weave_brain.core.config import Settings
from weave_brain.domain.models import ChatResponse, GraphView
from weave_brain.services.graph_service import AUTH, bounded_view


@pytest.fixture
def client():
    return TestClient(
        create_app(Settings(_env_file=None, development_fixtures=True)),
        raise_server_exceptions=False,
    )


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"question": " "},
        {"question": "a" * 4001},
        {"question": None},
        {"question": 4},
    ],
)
def test_chat_invalid(client, body):
    assert client.post("/api/chat", json=body).status_code == 400


@pytest.mark.parametrize(
    "question,intent",
    [
        ("Who owns authentication?", "service_overview"),
        ("What breaks if authentication goes down?", "blast_radius"),
        ("Tell me about sales", "unsupported"),
        ("Change impact of authentication", "change_impact"),
        ("Why do authentication tokens expire?", "decision_rationale"),
        ("Who are authentication experts?", "expert_finder"),
    ],
)
def test_chat_contract(client, question, intent):
    response = client.post("/api/chat", json={"question": question})
    assert response.status_code == 200, response.text
    result = ChatResponse.model_validate(response.json())
    assert result.intent == intent
    assert result.answer and result.message_id
    assert any("fixture" in warning.lower() for warning in result.warnings)
    if result.graph:
        ids = {n.id for n in result.graph.nodes}
        assert len(ids) == len(result.graph.nodes)
        assert all(
            e.source_id in ids and e.target_id in ids for e in result.graph.edges
        )
        assert len({e.id for e in result.graph.edges}) == len(result.graph.edges)


def test_overview_direction_and_nullability(client):
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
    assert result["evidence"][0]["source_url"] is None


def test_blast_direction(client):
    result = client.get(f"/api/services/{AUTH}/blast-radius").json()
    assert {n["id"] for n in result["affected_services"]} == {
        "service:user-profile-api",
        "service:notification-service",
    }
    assert all(e["target_id"] == AUTH for e in result["graph"]["edges"])
    assert result["evidence"]


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
def test_unknown_entity_never_fabricated(client, path):
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
    result = response.json()
    assert response.status_code == 200 and result["path_found"]
    assert result["graph"]["edges"][0]["source_id"] == "team:platform-engineering"
    assert len(result["graph"]["edges"]) <= 3


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


def test_fixture_mode_not_ready(client):
    assert client.get("/api/health").status_code == 503
    assert client.get("/api/live").status_code == 200


def test_no_production_fixture_fallback():
    client = TestClient(
        create_app(
            Settings(_env_file=None, development_fixtures=False, falkordb_host=None)
        ),
        raise_server_exceptions=False,
    )
    response = client.post("/api/chat", json={"question": "Who owns authentication?"})
    assert response.status_code == 503


def test_graph_bounds_and_dangling_edges():
    nodes = [
        {"id": f"service:n-{i}", "type": "service", "title": str(i)} for i in range(110)
    ]
    graph = bounded_view(
        {
            "nodes": nodes,
            "edges": [
                {
                    "source_id": "service:n-0",
                    "target_id": "service:missing",
                    "relationship_type": "DEPENDS_ON",
                }
            ],
        }
    )
    assert len(graph.nodes) == 100 and graph.truncated and graph.warning
    assert not graph.edges
    GraphView.model_validate_json(graph.model_dump_json())


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


def test_graph_log_redaction(caplog):
    create_app(Settings(_env_file=None))
    with caplog.at_level(logging.ERROR):
        logging.getLogger("weave_brain.graph.queries").error(
            "Query failed: %s", "password=hidden"
        )
    assert "password=hidden" not in caplog.text


def test_unexpected_errors_are_safe_and_cors_readable(monkeypatch, caplog):
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


def test_env_file_and_process_precedence(tmp_path, monkeypatch):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    env = tmp_path / ".env"
    env.write_text(
        'ALLOWED_ORIGINS=["https://example.com"]\nFALKORDB_HOST=file-host\nFALKORDB_GRAPH_NAME=demo\n'
    )
    monkeypatch.setenv("FALKORDB_HOST", "process-host")
    settings = Settings(_env_file=env)
    assert settings.falkordb_host == "process-host"
    assert settings.origins == ["https://example.com"]


@pytest.mark.parametrize(
    "origin",
    ["*", "[]", "https://user:password@example.com", "https://example.com/path"],
)
def test_invalid_origins_rejected(origin):
    with pytest.raises(ValueError):
        Settings(_env_file=None, allowed_origins=origin)


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
