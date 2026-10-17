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


def get_client(host: str | None = None, port: int | None = None) -> FalkorDB:
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

    return FalkorDB(host=host, port=port)


def get_graph(
    graph_name: str | None = None,
    host: str | None = None,
    port: int | None = None,
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

    client = get_client(host=host, port=port)
    return client.select_graph(graph_name)
