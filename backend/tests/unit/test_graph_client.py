"""Unit tests for FalkorDB client configuration and credential forwarding."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from pydantic import SecretStr

from weave_brain.core.config import Settings
from weave_brain.graph.client import ConfigurationError, get_client, get_graph
from weave_brain.services.graph_service import GraphService


def test_get_client_local_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify local development defaults (no auth, no SSL) are preserved."""
    monkeypatch.setenv("FALKORDB_HOST", "localhost")
    monkeypatch.setenv("FALKORDB_PORT", "6379")
    monkeypatch.delenv("FALKORDB_PASSWORD", raising=False)
    monkeypatch.delenv("FALKORDB_USERNAME", raising=False)
    monkeypatch.delenv("FALKORDB_SSL", raising=False)

    with patch("weave_brain.graph.client.FalkorDB") as mock_cls:
        client = get_client()
        mock_cls.assert_called_once_with(
            host="localhost",
            port=6379,
            password=None,
            username=None,
            ssl=False,
        )
        assert client == mock_cls.return_value


def test_get_client_auth_and_ssl_from_args() -> None:
    """Verify explicit keyword arguments for auth and TLS/SSL are forwarded."""
    with patch("weave_brain.graph.client.FalkorDB") as mock_cls:
        get_client(
            host="remote.falkordb.net",
            port=16379,
            password="secret_pass_123",
            username="admin_user",
            ssl=True,
        )
        mock_cls.assert_called_once_with(
            host="remote.falkordb.net",
            port=16379,
            password="secret_pass_123",
            username="admin_user",
            ssl=True,
        )


def test_get_client_auth_and_ssl_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify environment variables for auth and TLS/SSL are parsed and forwarded."""
    monkeypatch.setenv("FALKORDB_HOST", "cloud.falkordb.com")
    monkeypatch.setenv("FALKORDB_PORT", "12345")
    monkeypatch.setenv("FALKORDB_PASSWORD", "env_password_xyz")
    monkeypatch.setenv("FALKORDB_USERNAME", "env_user_abc")
    monkeypatch.setenv("FALKORDB_SSL", "true")

    with patch("weave_brain.graph.client.FalkorDB") as mock_cls:
        get_client()
        mock_cls.assert_called_once_with(
            host="cloud.falkordb.com",
            port=12345,
            password="env_password_xyz",
            username="env_user_abc",
            ssl=True,
        )


@pytest.mark.parametrize("ssl_val", ["false", "0", "no", "FALSE", "No"])
def test_get_client_ssl_falsy_env_values(
    monkeypatch: pytest.MonkeyPatch, ssl_val: str
) -> None:
    """Verify falsy string values in FALKORDB_SSL resolve to ssl=False."""
    monkeypatch.setenv("FALKORDB_HOST", "localhost")
    monkeypatch.setenv("FALKORDB_PORT", "6379")
    monkeypatch.setenv("FALKORDB_SSL", ssl_val)

    with patch("weave_brain.graph.client.FalkorDB") as mock_cls:
        get_client()
        _, kwargs = mock_cls.call_args
        assert kwargs["ssl"] is False


def test_get_client_empty_auth_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify empty string environment variables resolve to None."""
    monkeypatch.setenv("FALKORDB_HOST", "localhost")
    monkeypatch.setenv("FALKORDB_PORT", "6379")
    monkeypatch.setenv("FALKORDB_PASSWORD", "")
    monkeypatch.setenv("FALKORDB_USERNAME", "")

    with patch("weave_brain.graph.client.FalkorDB") as mock_cls:
        get_client()
        _, kwargs = mock_cls.call_args
        assert kwargs["password"] is None
        assert kwargs["username"] is None


def test_get_client_missing_host_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ConfigurationError when FALKORDB_HOST is missing."""
    monkeypatch.delenv("FALKORDB_HOST", raising=False)
    with pytest.raises(ConfigurationError, match="FALKORDB_HOST"):
        get_client()


def test_get_client_missing_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ConfigurationError when FALKORDB_PORT is missing."""
    monkeypatch.setenv("FALKORDB_HOST", "localhost")
    monkeypatch.delenv("FALKORDB_PORT", raising=False)
    with pytest.raises(ConfigurationError, match="FALKORDB_PORT"):
        get_client()


def test_get_client_invalid_port_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ConfigurationError when FALKORDB_PORT is not an integer."""
    monkeypatch.setenv("FALKORDB_HOST", "localhost")
    monkeypatch.setenv("FALKORDB_PORT", "not-a-number")
    with pytest.raises(ConfigurationError, match="must be an integer"):
        get_client()


def test_get_graph_forwards_credentials() -> None:
    """Verify get_graph forwards credentials and selects the named graph."""
    mock_client = MagicMock()
    with patch(
        "weave_brain.graph.client.get_client", return_value=mock_client
    ) as mock_gc:
        graph = get_graph(
            graph_name="prod_graph",
            host="prod.db",
            port=6380,
            password="pwd",
            username="usr",
            ssl=True,
        )
        mock_gc.assert_called_once_with(
            host="prod.db",
            port=6380,
            password="pwd",
            username="usr",
            ssl=True,
        )
        mock_client.select_graph.assert_called_once_with("prod_graph")
        assert graph == mock_client.select_graph.return_value


def test_get_graph_missing_graph_name_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify ConfigurationError when graph_name is missing."""
    monkeypatch.delenv("FALKORDB_GRAPH_NAME", raising=False)
    with pytest.raises(ConfigurationError, match="FALKORDB_GRAPH_NAME"):
        get_graph()


def test_graph_service_forwards_credentials_from_settings() -> None:
    """Verify GraphService extracts SecretStr password and forwards all settings."""
    settings = Settings(
        development_fixtures=False,
        falkordb_graph_name="cloud_graph",
        falkordb_host="cloud.falkordb.com",
        falkordb_port=16379,
        falkordb_username="cloud_user",
        falkordb_password=SecretStr("cloud_secret"),
        falkordb_ssl=True,
    )
    service = GraphService(settings)

    with patch("weave_brain.services.graph_service.get_graph") as mock_get_graph:
        service._graph()
        mock_get_graph.assert_called_once_with(
            graph_name="cloud_graph",
            host="cloud.falkordb.com",
            port=16379,
            password="cloud_secret",
            username="cloud_user",
            ssl=True,
        )


def test_graph_service_local_defaults_forwarded() -> None:
    """Verify GraphService cleanly passes None/False when no auth/ssl configured."""
    settings = Settings(
        development_fixtures=False,
        falkordb_graph_name="local_graph",
        falkordb_host="localhost",
        falkordb_port=6379,
        falkordb_username=None,
        falkordb_password=None,
        falkordb_ssl=False,
    )
    service = GraphService(settings)

    with patch("weave_brain.services.graph_service.get_graph") as mock_get_graph:
        service._graph()
        mock_get_graph.assert_called_once_with(
            graph_name="local_graph",
            host="localhost",
            port=6379,
            password=None,
            username=None,
            ssl=False,
        )
