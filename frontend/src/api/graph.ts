import type { GraphView, GraphNode } from "../types/api";
import { request } from "./client";

export const getNeighborhood = (id: string) =>
  request<GraphView>(`/graph/neighborhood/${encodeURIComponent(id)}?depth=1`);
export const getEntity = (id: string) =>
  request<GraphNode>(`/entities/${encodeURIComponent(id)}`);
export const searchEntities = (q: string) =>
  request<GraphNode[]>(`/search?${new URLSearchParams({ q })}`);

export const getConnection = (from: string, to: string) =>
  request<{ path_found: boolean; graph: GraphView }>(
    `/graph/shortest-path?${new URLSearchParams({ from_id: from, to_id: to })}`,
  );
