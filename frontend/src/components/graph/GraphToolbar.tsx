import { Icon } from "../Icon";
import { useState } from "react";
import { useReactFlow } from "@xyflow/react";
import { useGraphStore } from "../../store/graphStore";
import { colors } from "./colors";

export function GraphToolbar() {
  const [legend, setLegend] = useState(false);
  const flow = useReactFlow();
  const { graph, hidden, toggle } = useGraphStore();
  const types = [...new Set(graph.nodes.map((n) => n.type))];
  return (
    <div className="graph-toolbar">
      <div className="toolbar-buttons">
        <button onClick={() => flow.fitView({ padding: 0.18, maxZoom: 1 })}>
          <Icon name="fit" size={14} /> Fit view
        </button>
        <button aria-label="Zoom in" onClick={() => flow.zoomIn()}>
          <Icon name="plus" size={15} />
        </button>
        <button aria-label="Zoom out" onClick={() => flow.zoomOut()}>
          <Icon name="minus" size={15} />
        </button>
        <button aria-expanded={legend} onClick={() => setLegend(!legend)}>
          <Icon name="layers" size={14} /> Legend
        </button>
      </div>
      <div className="filters">
        {types.map((type) => (
          <button
            key={type}
            aria-label={`● ${type}`}
            aria-pressed={!hidden.has(type)}
            onClick={() => toggle(type)}
            style={{
              opacity: hidden.has(type) ? 0.4 : 1,
            }}
          >
            <span
              className="type-dot"
              style={{ background: colors[type] ?? "var(--entity-file)" }}
              aria-hidden="true"
            />{" "}
            {type}
          </button>
        ))}
      </div>
      {legend && (
        <p className="muted">
          Arrows follow stored relationships. Double-click to expand. Borders
          highlight evidence. Freshness: fresh &lt;30 days, aging 30–90, stale
          &gt;90; unknown without timestamps.
        </p>
      )}
    </div>
  );
}
