from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EntityType = Literal[
    "person",
    "team",
    "service",
    "repository",
    "file",
    "document",
    "decision",
    "ticket",
    "incident",
    "test",
    "project",
]


# Graph view - returned by backend, rendered by frontend
class GraphNode(BaseModel):
    id: str  # stable entity id
    type: EntityType
    title: str
    properties: dict[str, Any] = {}
    on_highlighted_path: bool = False
    is_stale: bool = False  # Added in Section 12 (Page 27)


class GraphEdge(BaseModel):
    id: str  # f"{source_id}::{rel_type}::{target_id}"
    source_id: str
    target_id: str
    relationship_type: str
    label: str
    properties: dict[str, Any] = {}


class GraphView(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    root_node_ids: list[str] = []
    highlighted_path_ids: list[str] = []
    truncated: bool = False
    warning: str | None = None


# Evidence
class EvidenceItem(BaseModel):
    source_id: str
    title: str
    source_type: str
    excerpt: str | None = None
    source_url: str | None = None
    relationship_path: list[str] = []  # list of node IDs


# Chat API
class ChatRequest(BaseModel):
    question: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    message_id: str = ""
    answer: str
    evidence: list[EvidenceItem] = []
    graph: GraphView | None = None
    highlighted_paths: list[list[str]] = []
    related_entities: list[GraphNode] = []
    suggested_followups: list[str] = []  # Added in Section 21 (Page 65) for Dev D
    warnings: list[str] = []
    intent: str | None = None

    def __init__(self, **data: Any):
        if not data.get("message_id"):
            data["message_id"] = str(uuid.uuid4())
        super().__init__(**data)


# Ingestion
# Supports (rel_type, target_canonical_id) or (rel_type, target_canonical_id, edge_props)
RelationshipEdge = tuple[str, str] | tuple[str, str, dict[str, Any]]


class SourceArtifact(BaseModel):
    source_id: str
    source_type: str
    entity_type: EntityType
    canonical_id: str  # stable graph node id
    title: str
    properties: dict[str, Any]
    relationships: list[RelationshipEdge] = (
        []
    )  # (rel_type, target_canonical_id[, props])
    source_url: str | None = None
    content_hash: str | None = None
    source_updated_at: datetime | None = None
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC)
    )


class SyncReport(BaseModel):
    source: str
    records_processed: int = 0
    nodes_created: int = 0
    nodes_updated: int = 0
    edges_created: int = 0
    errors: list[str] = []
    warnings: list[str] = []


# Added in Section 13 (Page 30) & Section 21 (Page 65-66) for Onboarding & Health
class OnboardingBrief(BaseModel):
    service_id: str
    service_title: str
    overview: str
    key_decisions: list[EvidenceItem] = []
    top_experts: list[GraphNode] = []
    change_risks: list[str] = []
    open_incidents: list[GraphNode] = []
    related_tickets: list[GraphNode] = []
    graph: GraphView | None = None
    warnings: list[str] = []


class KnowledgeGap(BaseModel):
    entity_id: str
    entity_title: str
    gap_type: Literal["no_owner", "missing_rationale", "undocumented"]


class HealthDimension(BaseModel):
    label: str
    score: float
    current: int
    total: int
    status: Literal["good", "warning", "critical"]


class HealthScore(BaseModel):
    dimensions: list[HealthDimension]
    overall: float
    gaps: list[KnowledgeGap] = []
