"""Graph package for weave_brain."""

from weave_brain.graph.client import ConfigurationError, get_client, get_graph
from weave_brain.graph.schema import (
    ENTITY_TYPE_TO_LABEL,
    IDENTITY_PROPERTY,
    WHITELISTED_LABELS,
    get_label_for_entity_type,
    init_schema,
)

__all__ = [
    "ENTITY_TYPE_TO_LABEL",
    "IDENTITY_PROPERTY",
    "WHITELISTED_LABELS",
    "ConfigurationError",
    "get_client",
    "get_graph",
    "get_label_for_entity_type",
    "init_schema",
]
