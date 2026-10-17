"""Graph schema definitions, entity-to-label mappings, and index initialization."""

from __future__ import annotations

from typing import Any

from redis.exceptions import ResponseError

from weave_brain.domain.models import EntityType

IDENTITY_PROPERTY = "id"

ENTITY_TYPE_TO_LABEL: dict[EntityType, str] = {
    "person": "Person",
    "team": "Team",
    "service": "Service",
    "repository": "Repository",
    "file": "File",
    "document": "Document",
    "decision": "Decision",
    "ticket": "Ticket",
    "incident": "Incident",
    "test": "Test",
    "project": "Project",
}

WHITELISTED_LABELS: frozenset[str] = frozenset(ENTITY_TYPE_TO_LABEL.values())


def get_label_for_entity_type(entity_type: EntityType | str) -> str:
    """Return the canonical PascalCase graph label for an EntityType.

    Raises KeyError if entity_type is not recognized.
    """
    if entity_type not in ENTITY_TYPE_TO_LABEL:
        raise KeyError(
            f"Unknown entity type: '{entity_type}'. Must be one of {sorted(ENTITY_TYPE_TO_LABEL.keys())}"
        )
    return ENTITY_TYPE_TO_LABEL[entity_type]  # type: ignore[index]


def get_existing_indexes(graph: Any) -> set[tuple[str, str]]:
    """Query existing indexes from FalkorDB and return set of (label, property_name) tuples."""
    res = graph.query("CALL db.indexes()")
    label_idx = 0
    props_idx = 1
    if hasattr(res, "header") and res.header:
        for idx, col in enumerate(res.header):
            if len(col) > 1:
                if col[1] == "label":
                    label_idx = idx
                elif col[1] == "properties":
                    props_idx = idx

    existing: set[tuple[str, str]] = set()
    for row in getattr(res, "result_set", []):
        if len(row) > max(label_idx, props_idx):
            label = row[label_idx]
            props = row[props_idx]
            if isinstance(props, list):
                for p in props:
                    existing.add((label, p))
            elif isinstance(props, str):
                existing.add((label, props))
    return existing


def init_schema(graph: Any) -> list[str]:
    """Initialize range indexes on identity property ('id') for all whitelisted entity labels.

    Idempotent: inspects existing indexes first and tolerates 'already indexed' responses.
    Raises ResponseError for any other unexpected database error.
    Returns the list of labels whose indexes were newly created or verified.
    """
    existing_indexes = get_existing_indexes(graph)
    initialized_labels: list[str] = []

    for label in sorted(WHITELISTED_LABELS):
        if label not in WHITELISTED_LABELS:
            continue

        if (label, IDENTITY_PROPERTY) in existing_indexes:
            initialized_labels.append(label)
            continue

        query = f"CREATE INDEX FOR (n:{label}) ON (n.{IDENTITY_PROPERTY})"
        try:
            graph.query(query)
            initialized_labels.append(label)
        except ResponseError as e:
            err_msg = str(e).lower()
            if "already indexed" in err_msg or "already exists" in err_msg:
                initialized_labels.append(label)
            else:
                raise

    return initialized_labels
