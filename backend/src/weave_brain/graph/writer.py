"""Idempotent graph writer for FalkorDB."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from weave_brain.domain.models import RelationshipEdge, SourceArtifact, SyncReport
from weave_brain.graph.client import get_graph
from weave_brain.graph.schema import (
    ENTITY_TYPE_TO_LABEL,
    get_label_for_entity_type,
)

# 14 Canonical relationship types frozen in docs/graph-schema.md
WHITELISTED_RELATIONSHIPS: frozenset[str] = frozenset({
    "OWNS",
    "MEMBER_OF",
    "MAINTAINS",
    "DEPENDS_ON",
    "IMPLEMENTED_IN",
    "CONTAINS",
    "IMPORTS",
    "DECIDES_FOR",
    "MOTIVATED_BY",
    "SUPERSEDES",
    "DOCUMENTS",
    "AFFECTS",
    "WORKED_ON",
    "USES",
})

RESERVED_NODE_KEYS: frozenset[str] = frozenset({
    "id",
    "canonical_id",
    "title",
    "source_id",
    "source_type",
    "ingested_at",
    "source_url",
    "content_hash",
    "source_updated_at",
})


def _sanitize_value(value: Any) -> Any:
    """Recursively convert datetimes to ISO strings and nested dicts to JSON."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return json.dumps(
            {k: _sanitize_value(v) for k, v in value.items() if v is not None}
        )
    if isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value if v is not None]
    return value


def normalize_relationship(
    edge: RelationshipEdge,
) -> tuple[str, str, dict[str, Any]]:
    """Normalize a 2-tuple or 3-tuple RelationshipEdge into (rel_type, target_id, edge_props).

    Validates that rel_type is in WHITELISTED_RELATIONSHIPS and target_id is non-empty.
    Sanitizes edge_props (converts datetimes to ISO format and strips None values).
    """
    if len(edge) == 2:
        rel_type, target_id = edge
        raw_props: dict[str, Any] = {}
    elif len(edge) == 3:
        rel_type, target_id, raw_props = edge
        if not isinstance(raw_props, dict):
            raise ValueError(
                f"Relationship edge properties must be a dict, got {type(raw_props).__name__}"
            )
    else:
        raise ValueError(
            f"Invalid RelationshipEdge tuple length: {len(edge)}. Expected 2 or 3 elements."
        )

    if not isinstance(rel_type, str) or not rel_type:
        raise ValueError("Relationship type must be a non-empty string.")
    if rel_type not in WHITELISTED_RELATIONSHIPS:
        raise ValueError(
            f"Invalid relationship type: '{rel_type}'. Must be one of {sorted(WHITELISTED_RELATIONSHIPS)}"
        )

    if not isinstance(target_id, str) or not target_id.strip():
        raise ValueError("Relationship target_id must be a non-empty string.")

    clean_props = {
        k: _sanitize_value(v) for k, v in raw_props.items() if v is not None
    }
    return (rel_type, target_id.strip(), clean_props)


def prepare_node_properties(artifact: SourceArtifact) -> dict[str, Any]:
    """Prepare and sanitize node properties from a SourceArtifact.

    Strips any reserved identity keys from artifact.properties to prevent collision,
    serializes datetimes and nested dicts, and injects top-level canonical fields.
    Preserves artifact.ingested_at for freshness/staleness calculation.
    """
    clean_props: dict[str, Any] = {}
    for k, v in artifact.properties.items():
        if k in RESERVED_NODE_KEYS:
            continue
        if v is None:
            continue
        clean_props[k] = _sanitize_value(v)

    # Inject canonical top-level fields
    clean_props["id"] = artifact.canonical_id
    clean_props["title"] = artifact.title
    clean_props["source_id"] = artifact.source_id
    clean_props["source_type"] = artifact.source_type
    clean_props["ingested_at"] = artifact.ingested_at.isoformat()

    if artifact.source_url is not None:
        clean_props["source_url"] = artifact.source_url
    if artifact.content_hash is not None:
        clean_props["content_hash"] = artifact.content_hash
    if artifact.source_updated_at is not None:
        clean_props["source_updated_at"] = (
            artifact.source_updated_at.isoformat()
        )

    return clean_props


def upsert_node(
    arg1: Any,
    arg2: Any = None,
    graph: Any = None,
) -> bool:
    """Upsert a single node in FalkorDB using MERGE on id.

    Supports both upsert_node(artifact, graph=...) and upsert_node(graph, artifact).
    Returns True if the node was created, False if matched/updated.
    """
    if isinstance(arg1, SourceArtifact):
        artifact = arg1
        active_graph = graph if graph is not None else arg2
    else:
        active_graph = arg1
        artifact = arg2

    if active_graph is None:
        active_graph = get_graph()

    label = get_label_for_entity_type(artifact.entity_type)
    props = prepare_node_properties(artifact)

    query = f"MERGE (n:{label} {{id: $id}}) SET n += $props RETURN n.id"
    res = active_graph.query(
        query, {"id": artifact.canonical_id, "props": props}
    )

    nodes_created = getattr(res, "nodes_created", 0)
    return bool(nodes_created and nodes_created > 0)


def upsert_relationship(
    source_id: str,
    rel_type: str,
    target_id: str,
    properties: dict[str, Any] | None = None,
    graph: Any = None,
) -> tuple[bool, bool]:
    """Upsert a directed relationship between two nodes.

    Uses entity prefixes when available to leverage range indexes.
    Returns (matched_endpoints: bool, created_edge: bool).
    """
    if graph is None:
        graph = get_graph()

    if rel_type not in WHITELISTED_RELATIONSHIPS:
        raise ValueError(
            f"Invalid relationship type: '{rel_type}'. Must be one of {sorted(WHITELISTED_RELATIONSHIPS)}"
        )

    # Use entity prefixes to attach labels for index optimization
    src_prefix = source_id.split(":")[0] if ":" in source_id else ""
    tgt_prefix = target_id.split(":")[0] if ":" in target_id else ""
    src_label = ENTITY_TYPE_TO_LABEL.get(src_prefix)  # type: ignore[arg-type]
    tgt_label = ENTITY_TYPE_TO_LABEL.get(tgt_prefix)  # type: ignore[arg-type]

    src_pattern = (
        f"(a:{src_label} {{id: $src_id}})" if src_label else "(a {id: $src_id})"
    )
    tgt_pattern = (
        f"(b:{tgt_label} {{id: $tgt_id}})" if tgt_label else "(b {id: $tgt_id})"
    )

    clean_props = {
        k: _sanitize_value(v)
        for k, v in (properties or {}).items()
        if v is not None
    }

    query = (
        f"MATCH {src_pattern}, {tgt_pattern} "
        f"MERGE (a)-[r:{rel_type}]->(b) "
        f"SET r += $props "
        f"RETURN type(r)"
    )
    res = graph.query(
        query,
        {
            "src_id": source_id,
            "tgt_id": target_id,
            "props": clean_props,
        },
    )

    matched = bool(getattr(res, "result_set", []))
    rels_created = getattr(res, "relationships_created", 0)
    created = bool(rels_created and rels_created > 0)

    return (matched, created)


# Alias
upsert_edge = upsert_relationship


def upsert_many(
    arg1: Any,
    arg2: Any = None,
    graph: Any = None,
    source_name: str = "seed",
) -> SyncReport:
    """Execute two-phase batch upsert of SourceArtifacts.

    Supports both upsert_many(artifacts, graph=..., source_name=...)
    and write_artifacts(graph, artifacts, source_name=...).

    Phase 1: Upsert all nodes.
    Phase 2: Upsert all relationships.
    Skips missing targets without creating phantom nodes, recording warnings.
    """
    if isinstance(arg1, list):
        artifacts = arg1
        active_graph = graph if graph is not None else arg2
    else:
        active_graph = arg1
        artifacts = arg2

    if active_graph is None:
        active_graph = get_graph()

    report = SyncReport(source=source_name)

    # Phase 1: Upsert all nodes
    for artifact in artifacts:
        try:
            created = upsert_node(artifact, graph=active_graph)
            report.records_processed += 1
            if created:
                report.nodes_created += 1
            else:
                report.nodes_updated += 1
        except (RedisConnectionError, ConnectionError, OSError):
            raise
        except (ResponseError, ValueError, TypeError, KeyError) as e:
            report.records_processed += 1
            report.errors.append(
                f"Failed to upsert node for artifact '{artifact.canonical_id}': {e}"
            )

    # Phase 2: Upsert all relationships
    for artifact in artifacts:
        for edge in artifact.relationships:
            try:
                rel_type, target_id, edge_props = normalize_relationship(edge)
                matched, created = upsert_relationship(
                    source_id=artifact.canonical_id,
                    rel_type=rel_type,
                    target_id=target_id,
                    properties=edge_props,
                    graph=active_graph,
                )
                if not matched:
                    report.warnings.append(
                        f"Skipped edge '{artifact.canonical_id} -[:{rel_type}]-> {target_id}': "
                        f"target node '{target_id}' not found in graph."
                    )
                elif created:
                    report.edges_created += 1
            except (RedisConnectionError, ConnectionError, OSError):
                raise
            except (ResponseError, ValueError, TypeError, KeyError) as e:
                report.errors.append(
                    f"Failed to upsert relationship '{artifact.canonical_id}' -> '{edge}': {e}"
                )

    return report


# Alias
write_artifacts = upsert_many
