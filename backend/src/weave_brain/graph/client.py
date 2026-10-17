"""FalkorDB client connection management and configuration."""

from __future__ import annotations

import os
from typing import Any

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from falkordb import FalkorDB


class ConfigurationError(Exception):
    """Raised when required FalkorDB configuration variables are missing or invalid."""


def get_client(
    host: str | None = None,
    port: int | None = None,
    *,
    username: str | None = None,
    password: str | None = None,
    ssl: bool | None = None,
    timeout: float | None = None,
) -> FalkorDB:
    """Create and return a FalkorDB client instance.

    Reads FALKORDB_HOST and FALKORDB_PORT from environment if not explicitly passed.
    Raises ConfigurationError if any required setting is missing or invalid.
    """
    if host is None:
        host = os.getenv("FALKORDB_HOST")
        if not host:
            raise ConfigurationError(
                "Missing required environment variable: FALKORDB_HOST"
            )

    if port is None:
        port_env = os.getenv("FALKORDB_PORT")
        if not port_env:
            raise ConfigurationError(
                "Missing required environment variable: FALKORDB_PORT"
            )
        try:
            port = int(port_env)
        except ValueError:
            raise ConfigurationError(
                f"Invalid FALKORDB_PORT: '{port_env}' must be an integer"
            )

    return FalkorDB(
        host=host,
        port=port,
        username=username if username is not None else os.getenv("FALKORDB_USERNAME"),
        password=password if password is not None else os.getenv("FALKORDB_PASSWORD"),
        ssl=ssl
        if ssl is not None
        else os.getenv("FALKORDB_SSL", "false").lower() == "true",
        ssl_check_hostname=True,
        socket_timeout=timeout
        if timeout is not None
        else float(os.getenv("FALKORDB_TIMEOUT", "5")),
        socket_connect_timeout=timeout
        if timeout is not None
        else float(os.getenv("FALKORDB_TIMEOUT", "5")),
    )


def get_graph(
    graph_name: str | None = None,
    host: str | None = None,
    port: int | None = None,
    **connection_options: Any,
) -> Any:
    """Select and return a FalkorDB graph instance.

    Reads FALKORDB_GRAPH_NAME from environment if not explicitly passed.
    Raises ConfigurationError if FALKORDB_GRAPH_NAME, FALKORDB_HOST, or FALKORDB_PORT
    is missing or invalid.
    """
    if graph_name is None:
        graph_name = os.getenv("FALKORDB_GRAPH_NAME")
        if not graph_name:
            raise ConfigurationError(
                "Missing required environment variable: FALKORDB_GRAPH_NAME"
            )

    client = get_client(host=host, port=port, **connection_options)
    return client.select_graph(graph_name)
