import dagre from "@dagrejs/dagre";
import type { GraphView } from "../../types/api";

export function layoutGraph(graph: GraphView, intent: string, compact = false) {
  const width = compact ? 164 : 200;
  const g = new dagre.graphlib.Graph();
  g.setGraph({
    rankdir: intent === "decision_rationale" ? "TB" : "LR",
    nodesep: compact ? 18 : 30,
    ranksep: compact ? 50 : 75,
  });
  g.setDefaultEdgeLabel(() => ({}));
  graph.nodes.forEach((n) => g.setNode(n.id, { width, height: 88 }));
  graph.edges.forEach((e) => g.setEdge(e.source_id, e.target_id));
  dagre.layout(g);
  return new Map(
    graph.nodes.map((n) => {
      const p = g.node(n.id);
      return [n.id, { x: p.x - width / 2, y: p.y - 44 }];
    }),
  );
}
