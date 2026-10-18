import { Icon } from "../Icon";
import { useState } from "react";
import { useReactFlow, useViewport } from "@xyflow/react";
import { useGraphStore } from "../../store/graphStore";
import { colors } from "./colors";
import { EntityFinder } from "./EntityFinder";

export function GraphToolbar({
  expanded,
  onToggleExpanded,
}: {
  expanded: boolean;
  onToggleExpanded: () => void;
}) {
  const [legend, setLegend] = useState(false);
  const flow = useReactFlow();
  const { zoom } = useViewport();
  const { graph, hidden, toggle, focus, highlight, select } = useGraphStore();
  const types = [...new Set(graph.nodes.map((n) => n.type))];
  return (
    <div className="graph-toolbar">
      <div className="graph-control-row">
        <div
          className="toolbar-buttons"
          role="group"
          aria-label="Graph controls"
        >
          <button
            aria-label="Fit view"
            title="Fit view"
            onClick={() => flow.fitView({ padding: 0.18, maxZoom: 1 })}
          >
            <Icon name="fit" size={14} />{" "}
            <span className="control-label">Fit view</span>
          </button>
          <button aria-label="Zoom in" onClick={() => flow.zoomIn()}>
            <Icon name="plus" size={15} />
          </button>
          <button aria-label="Zoom out" onClick={() => flow.zoomOut()}>
            <Icon name="minus" size={15} />
          </button>
          <button
            className="zoom-level"
            aria-label="Reset zoom to 100 percent"
            title="Reset zoom to 100%"
            onClick={() => flow.zoomTo(1)}
          >
            {Math.round(zoom * 100)}%
          </button>
          <button
            aria-expanded={legend}
            aria-label="Legend"
            title="Legend"
            aria-controls="graph-legend"
            onClick={() => setLegend(!legend)}
          >
            <Icon name="layers" size={14} />{" "}
            <span className="control-label">Legend</span>
          </button>
          <button
            aria-label={expanded ? "Restore workspace" : "Maximize graph"}
            aria-pressed={expanded}
            onClick={onToggleExpanded}
            title={expanded ? "Restore workspace · Esc" : "Maximize graph"}
          >
            <Icon name={expanded ? "collapse" : "expand"} size={15} />
          </button>
        </div>
        <EntityFinder
          nodes={graph.nodes}
          onChoose={(id) => {
            highlight([id]);
            select(id);
            void flow.fitView({
              nodes: [{ id }],
              minZoom: 1,
              maxZoom: 1,
              padding: 0.3,
            });
          }}
        />
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
      {focus.length > 0 && (
        <button className="clear-focus" onClick={() => highlight([])}>
          <Icon name="close" size={12} /> Show all entities
        </button>
      )}
      {legend && (
        <p className="muted graph-legend" id="graph-legend">
          Arrows follow stored relationships. Double-click to expand. Borders
          highlight evidence. Freshness: fresh &lt;30 days, aging 30–90, stale
          &gt;90; unknown without timestamps.
        </p>
      )}
    </div>
  );
}
