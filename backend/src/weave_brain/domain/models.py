from __future__ import annotations
from pydantic import BaseModel
from typing import Optional, Literal, Any, Union
from datetime import datetime
import uuid

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
    warning: Optional[str] = None


# Evidence
class EvidenceItem(BaseModel):
    source_id: str
    title: str
    source_type: str
    excerpt: Optional[str] = None
    source_url: Optional[str] = None
    relationship_path: list[str] = []  # list of node IDs


# Chat API
class ChatRequest(BaseModel):
    question: str
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    message_id: str = ""
    answer: str
    evidence: list[EvidenceItem] = []
    graph: Optional[GraphView] = None
    highlighted_paths: list[list[str]] = []
    related_entities: list[GraphNode] = []
    suggested_followups: list[str] = []  # Added in Section 21 (Page 65) for Dev D
    warnings: list[str] = []
    intent: Optional[str] = None

    def __init__(self, **data: Any):
        if not data.get("message_id"):
            data["message_id"] = str(uuid.uuid4())
        super().__init__(**data)


# Ingestion
# Supports (rel_type, target_canonical_id) or (rel_type, target_canonical_id, edge_props)
RelationshipEdge = Union[tuple[str, str], tuple[str, str, dict[str, Any]]]


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
    source_url: Optional[str] = None
    content_hash: Optional[str] = None
    source_updated_at: Optional[datetime] = None
    ingested_at: datetime = datetime.utcnow()


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
    graph: Optional[GraphView] = None
    warnings: list[str] = []
