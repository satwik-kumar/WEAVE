export type EntityType =
  | "person"
  | "team"
  | "service"
  | "repository"
  | "file"
  | "document"
  | "decision"
  | "ticket"
  | "incident"
  | "test"
  | "project";

export interface GraphNode {
  id: string;
  type: EntityType;
  title: string;
  properties: Record<string, unknown>;
  on_highlighted_path: boolean;
  is_stale?: boolean;
}

export interface GraphEdge {
  id: string;
  source_id: string;
  target_id: string;
  relationship_type: string;
  label: string;
  properties: Record<string, unknown>;
}

export interface GraphView {
  nodes: GraphNode[];
  edges: GraphEdge[];
  root_node_ids: string[];
  highlighted_path_ids: string[];
  truncated: boolean;
  warning?: string | null;
}

export interface EvidenceItem {
  source_id: string;
  title: string;
  source_type: string;
  excerpt?: string | null;
  source_url?: string | null;
  relationship_path: string[];
}

export interface ChatRequest {
  question: string;
  conversation_id?: string | null;
}

export interface ChatResponse {
  message_id: string;
  answer: string;
  evidence: EvidenceItem[];
  graph?: GraphView | null;
  highlighted_paths: string[][];
  related_entities: GraphNode[];
  suggested_followups?: string[];
  warnings: string[];
  intent?: string | null;
}

export interface OnboardingBrief {
  service_id: string;
  service_title: string;
  overview: string;
  key_decisions: EvidenceItem[];
  top_experts: GraphNode[];
  change_risks: string[];
  open_incidents: GraphNode[];
  related_tickets: GraphNode[];
  graph?: GraphView | null;
  warnings: string[];
}

export interface KnowledgeGaps {
  unowned_services: GraphNode[];
  decisions_missing_rationale: GraphNode[];
  undocumented_services: GraphNode[];
  total_gaps: number;
  truncated?: boolean;
  warning?: string | null;
}

export interface HealthReport {
  health_score: number;
  metrics: {
    services_owned: number;
    decisions_rationale: number;
    incidents_resolved: number;
    services_documented: number;
  };
  counts: Record<string, number>;
  gaps: KnowledgeGaps;
  graph?: GraphView | null;
  warnings: string[];
}

export interface DecisionReport {
  nodes: GraphNode[];
  evidence: EvidenceItem[];
  graph: GraphView;
}
