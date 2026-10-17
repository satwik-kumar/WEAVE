import { create } from "zustand";
import type { GraphNode, GraphView } from "../types/api";

const empty: GraphView = {
  nodes: [],
  edges: [],
  root_node_ids: [],
  highlighted_path_ids: [],
  truncated: false,
};

export function cleanGraph(graph: GraphView): GraphView {
  const uniqueNodes = [...new Map(graph.nodes.map((n) => [n.id, n])).values()];
  const roots = new Set(graph.root_node_ids);
  const nodes = uniqueNodes
    .sort((a, b) => Number(!roots.has(a.id)) - Number(!roots.has(b.id)))
    .slice(0, 100);
  const ids = new Set(nodes.map((n) => n.id));
  const edges = [...new Map(graph.edges.map((e) => [e.id, e])).values()];
  const valid = edges.filter(
    (e) => ids.has(e.source_id) && ids.has(e.target_id),
  );
  const warning = [
    graph.warning,
    edges.length !== valid.length
      ? "Upstream graph has missing endpoints; those edges were omitted."
      : "",
    uniqueNodes.length > 100 ? "Graph limited to 100 nodes." : "",
  ]
    .filter(Boolean)
    .join(" ");
  return {
    ...graph,
    nodes,
    edges: valid,
    root_node_ids: graph.root_node_ids.filter((id) => ids.has(id)),
    truncated: graph.truncated || uniqueNodes.length > 100,
    warning,
  };
}

export function mergeGraph(current: GraphView, incoming: GraphView): GraphView {
  return cleanGraph({
    ...incoming,
    nodes: [...current.nodes, ...incoming.nodes],
    edges: [...current.edges, ...incoming.edges],
    root_node_ids: [
      ...new Set([...current.root_node_ids, ...incoming.root_node_ids]),
    ],
    highlighted_path_ids: [
      ...new Set([
        ...current.highlighted_path_ids,
        ...incoming.highlighted_path_ids,
      ]),
    ],
    truncated: current.truncated || incoming.truncated,
    warning: [
      ...new Set([current.warning, incoming.warning].filter(Boolean)),
    ].join(" "),
  });
}

interface GraphState {
  context: "ask" | "health" | "onboarding";
  setContext: (context: "ask" | "health" | "onboarding") => void;
  graph: GraphView;
  selected: string | null;
  hidden: Set<string>;
  focus: string[];
  focusEdges: Set<string>;
  expanding: Set<string>;
  version: number;
  intent: string;
  replace: (
    graph: GraphView | null | undefined,
    intent?: string | null,
    paths?: string[][],
  ) => void;
  merge: (graph: GraphView, version: number) => void;
  select: (id: string | null) => void;
  toggle: (type: string) => void;
  highlight: (ids: string[]) => void;
  expansion: (id: string, active: boolean) => void;
}

export const useGraphStore = create<GraphState>((set) => ({
  context: "ask",
  setContext: (context) =>
    set((state) => ({
      context,
      version: state.version + 1,
      selected: null,
      expanding: new Set(),
    })),
  graph: empty,
  selected: null,
  hidden: new Set(),
  focus: [],
  focusEdges: new Set(),
  expanding: new Set(),
  version: 0,
  intent: "",
  replace: (graph, intent, paths = []) =>
    set((s) => {
      const cleaned = cleanGraph(graph ?? empty);
      const focus = validFocus(cleaned, paths.flat());
      return {
        graph: cleaned,
        selected: null,
        hidden: new Set(),
        focus,
        focusEdges: pathEdges(cleaned, paths),
        expanding: new Set(),
        version: s.version + 1,
        intent: intent ?? "",
      };
    }),
  merge: (graph, version) =>
    set((s) =>
      s.version === version ? { graph: mergeGraph(s.graph, graph) } : {},
    ),
  select: (selected) => set({ selected }),
  toggle: (type) =>
    set((s) => {
      const hidden = new Set(s.hidden);
      if (hidden.has(type)) hidden.delete(type);
      else hidden.add(type);
      return { hidden };
    }),
  highlight: (focus) =>
    set((s) => {
      const graph = { ...s.graph };
      return {
        graph,
        focus: validFocus(graph, focus),
        focusEdges: pathEdges(s.graph, [focus]),
        hidden: new Set(),
      };
    }),
  expansion: (id, active) =>
    set((s) => {
      const expanding = new Set(s.expanding);
      if (active) expanding.add(id);
      else expanding.delete(id);
      return { expanding };
    }),
}));

function validFocus(graph: GraphView, ids: string[]): string[] {
  const known = new Set(graph.nodes.map((node) => node.id));
  const focus = ids.filter((id) => known.has(id));
  if (focus.length !== ids.length)
    graph.warning = [
      graph.warning,
      "Some evidence path entities were not returned by the backend.",
    ]
      .filter(Boolean)
      .join(" ");
  return focus;
}

function pathEdges(graph: GraphView, paths: string[][]): Set<string> {
  return new Set(
    graph.edges
      .filter((edge) =>
        paths.some((path) =>
          path.some(
            (id, i) =>
              i + 1 < path.length &&
              ((edge.source_id === id && edge.target_id === path[i + 1]) ||
                (edge.target_id === id && edge.source_id === path[i + 1])),
          ),
        ),
      )
      .map((edge) => edge.id),
  );
}

export function freshness(node: GraphNode): string {
  const value =
    node.properties.ingested_at ?? node.properties.source_updated_at;
  const stamp = typeof value === "string" ? Date.parse(value) : NaN;
  if (!Number.isFinite(stamp)) return "unknown";
  const days = (Date.now() - stamp) / 86400000;
  return days > 90 ? "stale" : days >= 30 || node.is_stale ? "aging" : "fresh";
}
