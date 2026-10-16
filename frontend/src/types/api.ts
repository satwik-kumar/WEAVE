export type EntityType =
  | 'person' | 'team' | 'service' | 'repository'
  | 'file' | 'document' | 'decision' | 'ticket'
  | 'incident' | 'test' | 'project';

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
  warning?: string;
}

export interface EvidenceItem {
  source_id: string;
  title: string;
  source_type: string;
  excerpt?: string;
  source_url?: string;
  relationship_path: string[];
}

export interface ChatRequest {
  question: string;
  conversation_id?: string;
}

export interface ChatResponse {
  message_id: string;
  answer: string;
  evidence: EvidenceItem[];
  graph?: GraphView;
  highlighted_paths: string[][];
  related_entities: GraphNode[];
  suggested_followups?: string[];
  warnings: string[];
  intent?: string;
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
  graph?: GraphView;
  warnings: string[];
}
