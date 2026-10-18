import { Icon } from "../Icon";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  Background,
  Handle,
  MarkerType,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  useNodesInitialized,
} from "@xyflow/react";
import type { NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { getNeighborhood, getConnection } from "../../api/graph";
import { freshness, useGraphStore } from "../../store/graphStore";
import { useChatStore } from "../../store/chatStore";
import type { GraphNode } from "../../types/api";
import { GraphToolbar } from "./GraphToolbar";
import { colors } from "./colors";
import { layoutGraph } from "./layout";
import { EntityDetailPanel } from "./EntityDetailPanel";

function EntityNode({ data, selected }: NodeProps) {
  const node = data.entity as GraphNode;
  return (
    <div
      className={`entity-node ${selected ? "selected" : ""} ${data.added ? "node-added" : ""}`}
      style={
        {
          "--entity-color": colors[node.type] ?? "var(--entity-file)",
          borderColor: data.highlight ? "var(--edge-focus)" : undefined,
        } as React.CSSProperties
      }
      title={`${node.title}\n${node.id}\n${data.relationshipCount} relationships\nSource: ${node.properties.source_id ?? "unknown"}\nFreshness: ${freshness(node)}`}
    >
      <Handle
        type="target"
        position={data.topDown ? Position.Top : Position.Left}
      />
      <div className="node-type">
        <Icon name={node.type} size={15} />
        <small>{node.type}</small>
        {data.highlight ? (
          <span className="path-marker" title="Evidence path" />
        ) : null}
      </div>
      <strong>{node.title}</strong>
      <span data-freshness={freshness(node)}>
        {data.pending ? "Expanding neighborhood..." : freshness(node)}
      </span>
      <Handle
        type="source"
        position={data.topDown ? Position.Bottom : Position.Right}
      />
    </div>
  );
}
const nodeTypes = { entity: EntityNode };

function Canvas() {
  const state = useGraphStore();
  const [expanded, setExpanded] = useState(false);
  const panelRef = useRef<HTMLElement>(null);
  const camera = useRef({ version: -1, focus: state.focus, targeted: false });
  useEffect(() => {
    if (!expanded) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const siblings = [
      ...document.querySelectorAll<HTMLElement>(
        ".app-sidebar, .app-header, .chat-panel, .report-content, .skip-link",
      ),
    ];
    const previous = siblings.map((element) => element.inert);
    siblings.forEach((element) => {
      element.inert = true;
    });
    return () => {
      document.body.style.overflow = previousOverflow;
      siblings.forEach((element, i) => {
        element.inert = previous[i];
      });
    };
  }, [expanded]);
  const [added, setAdded] = useState({ version: -1, ids: new Set<string>() });
  useEffect(() => {
    if (!added.ids.size) return;
    const timer = setTimeout(
      () => setAdded({ version: -1, ids: new Set() }),
      250,
    );
    return () => clearTimeout(timer);
  }, [added]);
  const loading = useChatStore((s) => s.loading);
  const answered = useChatStore((s) => s.messages.length > 0);
  const reduced = useReducedMotion();
  const [compact, setCompact] = useState(window.innerWidth <= 760);
  const [failure, setFailure] = useState({ message: "", version: -1 });
  const error = failure.version === state.version ? failure.message : "";
  function setError(message: string) {
    setFailure({ message, version: useGraphStore.getState().version });
  }
  const [hover, setHover] = useState("");
  const [menuState, setMenuState] = useState<{
    id: string;
    x: number;
    y: number;
    version: number;
  } | null>(null);
  const menu = menuState?.version === state.version ? menuState : null;
  function setMenu(value: { id: string; x: number; y: number } | null) {
    setMenuState(
      value ? { ...value, version: useGraphStore.getState().version } : null,
    );
  }
  const [connectionState, setConnectionState] = useState<{
    id: string;
    version: number;
  } | null>(null);
  const connectionFrom =
    connectionState?.version === state.version ? connectionState.id : null;
  function setConnectionFrom(id: string | null) {
    setConnectionState(
      id ? { id, version: useGraphStore.getState().version } : null,
    );
  }
  const [connecting, setConnecting] = useState(false);
  const selectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  function cancelSelection() {
    if (selectTimer.current) clearTimeout(selectTimer.current);
  }
  useEffect(() => () => cancelSelection(), []);
  const flow = useReactFlow();
  const nodesInitialized = useNodesInitialized();
  const canvasRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = canvasRef.current;
    if (!element) return;
    let timer: ReturnType<typeof setTimeout>;
    const observer = new ResizeObserver(() => {
      setCompact(window.innerWidth <= 760);
      clearTimeout(timer);
      timer = setTimeout(() => {
        const focus = camera.current.targeted
          ? useGraphStore.getState().focus
          : [];
        void flow.fitView({
          ...(focus.length ? { nodes: focus.map((id) => ({ id })) } : {}),
          padding: window.innerWidth <= 760 ? 0.04 : 0.18,
          minZoom: window.innerWidth <= 760 ? 0.8 : 0.15,
          maxZoom: 1,
        });
      }, 120);
    });
    observer.observe(element);
    return () => {
      observer.disconnect();
      clearTimeout(timer);
    };
  }, [flow]);
  useEffect(() => {
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenu(null);
        setConnectionFrom(null);
        if (!useGraphStore.getState().selected) setExpanded(false);
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, []);
  const { nodes, edges } = useMemo(() => {
    const visible = state.graph.nodes.filter((n) => !state.hidden.has(n.type));
    const ids = new Set(visible.map((n) => n.id));
    const focus = new Set(
      state.focus.length
        ? state.focus
        : state.graph.nodes
            .filter((n) => n.on_highlighted_path)
            .map((n) => n.id),
    );
    const highlighted = new Set(state.graph.highlighted_path_ids);
    const positions = layoutGraph(
      {
        ...state.graph,
        nodes: visible,
        edges: state.graph.edges.filter(
          (e) => ids.has(e.source_id) && ids.has(e.target_id),
        ),
      },
      state.intent,
      compact,
    );
    const nodes = visible.map((n) => {
      const position = positions.get(n.id)!;
      return {
        id: n.id,
        type: "entity",
        position,
        selected: state.selected === n.id,
        data: {
          topDown: state.intent === "decision_rationale",
          entity: n,
          added: added.version === state.version && added.ids.has(n.id),
          pending: state.expanding.has(n.id),
          highlight: focus.has(n.id) || n.on_highlighted_path,
          relationshipCount: state.graph.edges.filter(
            (e) => e.source_id === n.id || e.target_id === n.id,
          ).length,
        },
        style: { opacity: focus.size && !focus.has(n.id) ? 0.7 : 1 },
      };
    });
    const edges = state.graph.edges
      .filter((e) => ids.has(e.source_id) && ids.has(e.target_id))
      .map((e) => {
        const onPath = highlighted.has(e.id) || state.focusEdges.has(e.id);
        return {
          id: e.id,
          source: e.source_id,
          target: e.target_id,
          label: e.label,
          data: { ...e },
          animated: false,
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: onPath ? "var(--edge-focus)" : "var(--edge)",
          },
          style: {
            stroke: onPath ? "var(--edge-focus)" : "var(--edge)",
            strokeWidth: onPath ? 2 : 1.2,
          },
          labelStyle: {
            fill: "var(--edge-label)",
            fontSize: 11,
            fontFamily: "inherit",
          },
          labelBgStyle: { fill: "var(--canvas)" },
        };
      });
    return { nodes, edges };
  }, [
    state.graph,
    state.hidden,
    state.focus,
    state.focusEdges,
    state.selected,
    state.intent,
    compact,
    state.expanding,
    added,
    state.version,
  ]);
  useEffect(() => {
    const previous = camera.current;
    if (previous.version !== state.version) previous.targeted = false;
    else if (previous.focus !== state.focus)
      previous.targeted = state.focus.length > 0;
    previous.version = state.version;
    previous.focus = state.focus;
  }, [state.version, state.focus]);
  useEffect(() => {
    if (!nodesInitialized) return;
    const focus = camera.current.targeted ? state.focus : [];
    const timer = setTimeout(() => {
      const target = focus.length === 1 ? flow.getNode(focus[0]) : undefined;
      if (target && !compact) {
        return flow.setCenter(
          target.position.x +
            100 +
            Math.min(180, (canvasRef.current?.clientWidth ?? 0) * 0.25),
          target.position.y + 54,
          { zoom: 1 },
        );
      }
      return flow.fitView({
        ...(focus.length ? { nodes: focus.map((id) => ({ id })) } : {}),
        padding: focus.length ? 0.3 : compact ? 0.04 : 0.12,
        minZoom: focus.length === 1 ? 1 : compact ? 0.8 : 0.15,
        maxZoom: 1,
      });
    }, 80);
    return () => clearTimeout(timer);
  }, [
    state.graph,
    state.hidden,
    state.focus,
    state.version,
    flow,
    nodesInitialized,
    compact,
  ]);

  async function expand(id: string) {
    const snapshot = useGraphStore.getState();
    if (snapshot.expanding.has(id) || useChatStore.getState().loading) return;
    const version = snapshot.version;
    snapshot.expansion(id, true);
    setError("");
    try {
      const result = await getNeighborhood(id);
      if (useGraphStore.getState().version !== version) return;
      const existing = new Set(
        useGraphStore.getState().graph.nodes.map((node) => node.id),
      );
      setAdded({
        version,
        ids: new Set(
          result.nodes
            .filter((node) => !existing.has(node.id))
            .map((node) => node.id),
        ),
      });
      snapshot.merge(result, version);
    } catch (e) {
      if (useGraphStore.getState().version === version)
        setError(e instanceof Error ? e.message : "Expansion failed.");
    } finally {
      if (useGraphStore.getState().version === version)
        snapshot.expansion(id, false);
    }
  }
  function beginConnection(id: string) {
    cancelSelection();
    setConnectionFrom(id);
    setMenu(null);
    state.select(null);
    setError("");
  }
  async function connect(to: string) {
    if (!connectionFrom || connecting || loading) return;
    const version = useGraphStore.getState().version;
    setConnecting(true);
    setError("");
    try {
      const result = await getConnection(connectionFrom, to);
      if (useGraphStore.getState().version !== version) return;
      if (result.path_found)
        useGraphStore.getState().replace(result.graph, "connection");
      else
        setError(
          result.graph.warning || "No connection found in the bounded graph.",
        );
    } catch (failure) {
      if (useGraphStore.getState().version === version)
        setError(
          failure instanceof Error
            ? failure.message
            : "Connection lookup failed.",
        );
    } finally {
      setConnecting(false);
      setConnectionFrom(null);
    }
  }
  return (
    <section
      ref={panelRef}
      className={`graph-panel ${expanded ? "is-expanded" : ""}`}
      aria-label="Knowledge graph"
      role={expanded ? "dialog" : undefined}
      aria-modal={expanded ? true : undefined}
      onKeyDown={(event) => {
        if (!expanded || event.key !== "Tab") return;
        const controls = [
          ...panelRef.current!.querySelectorAll<HTMLElement>(
            'button:not(:disabled), input:not(:disabled), a[href], [tabindex="0"]',
          ),
        ].filter((element) => element.getClientRects().length > 0);
        const first = controls[0],
          last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
    >
      <div className="panel-heading">
        <div>
          <h2>
            <Icon name="graph" size={17} /> Evidence graph
          </h2>
        </div>
        <span>
          {nodes.length} entities · {edges.length} relationships
        </span>
      </div>
      <GraphToolbar
        expanded={expanded}
        onToggleExpanded={() => setExpanded((value) => !value)}
      />
      {connectionFrom && (
        <p className="connection-notice">
          From {connectionFrom}: select another entity.{" "}
          <button onClick={() => setConnectionFrom(null)}>
            Cancel connection
          </button>
        </p>
      )}
      {connecting && (
        <p role="status" className="connection-notice">
          Finding a connection…
        </p>
      )}
      <AnimatePresence
        custom={
          reduced || document.documentElement.dataset.input === "keyboard"
        }
      >
        {menu && (
          <motion.div
            className="graph-context-menu"
            role="menu"
            initial={{ opacity: 0, transform: "scale(0.97)" }}
            animate={{ opacity: 1, transform: "scale(1)" }}
            variants={{
              closed: (instant: boolean) => ({
                opacity: 0,
                transform: instant ? "scale(1)" : "scale(0.99)",
                transition: { duration: instant ? 0 : 0.1 },
              }),
            }}
            exit="closed"
            transition={{
              duration:
                reduced || document.documentElement.dataset.input === "keyboard"
                  ? 0
                  : 0.15,
              ease: [0.22, 1, 0.36, 1],
            }}
            style={{
              transformOrigin: "top left",
              left: Math.max(8, Math.min(menu.x, window.innerWidth - 220)),
              top: Math.max(8, Math.min(menu.y, window.innerHeight - 80)),
            }}
          >
            <button role="menuitem" onClick={() => beginConnection(menu.id)}>
              Start connection here
            </button>
          </motion.div>
        )}
      </AnimatePresence>
      {state.graph.warning && (
        <p role="status" className="notice">
          {state.graph.warning}
        </p>
      )}
      {state.graph.truncated && (
        <p className="notice">
          Results truncated. Expand an entity to explore further.
        </p>
      )}
      {(loading || state.expanding.size > 0) && (
        <p role="status" className="notice">
          {loading ? "Retrieving answer and graph…" : "Expanding neighborhood…"}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          {error} Double-click the node to retry.
        </p>
      )}
      {hover && <p className="muted edge-hover">{hover}</p>}
      <div className="canvas" ref={canvasRef}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.15}
          maxZoom={2}
          nodesDraggable={false}
          nodesConnectable={false}
          zoomOnDoubleClick={false}
          autoPanOnNodeFocus={false}
          onNodeClick={(_, n) => {
            setMenu(null);
            if (connectionFrom && n.id !== connectionFrom) {
              void connect(n.id);
              return;
            }
            if (_.ctrlKey || _.metaKey) {
              beginConnection(n.id);
              return;
            }
            cancelSelection();
            const version = state.version;
            selectTimer.current = setTimeout(() => {
              if (useGraphStore.getState().version === version)
                state.select(n.id);
            }, 250);
          }}
          onPaneClick={() => {
            setMenu(null);
            cancelSelection();
            state.select(null);
          }}
          onNodeContextMenu={(event, node) => {
            event.preventDefault();
            cancelSelection();
            setMenu({ id: node.id, x: event.clientX, y: event.clientY });
          }}
          onNodeDoubleClick={(_, n) => {
            cancelSelection();
            state.select(n.id);
            void expand(n.id);
          }}
          onEdgeMouseEnter={(_, e) =>
            setHover(`${e.source} → ${e.label} → ${e.target}`)
          }
          onEdgeMouseLeave={() => setHover("")}
        >
          <Background color="var(--canvas-dot)" gap={28} size={1} />
        </ReactFlow>
        {!nodes.length && (
          <div className="canvas-empty">
            <span className="empty-graph-icon">
              <Icon name="graph" size={32} />
            </span>
            <strong>
              {state.graph.nodes.length
                ? "No entities visible"
                : answered && state.context === "ask"
                  ? "No graph evidence returned"
                  : "Context, connected."}
            </strong>
            <small>
              {state.graph.nodes.length
                ? "Use the entity filters above to bring your graph back into view."
                : answered && state.context === "ask"
                  ? "This answer has no connected entities. Review its sources or try another question."
                  : "Ask a question to explore the people, services and decisions behind your answer."}
            </small>
          </div>
        )}
      </div>
      <div className="graph-help">
        <span>
          {compact
            ? "Pan to explore · Fit view for overview"
            : "Drag to pan · Scroll to zoom"}
        </span>
        <span>
          {connectionFrom
            ? "Click a node to connect · Esc to cancel"
            : "Double-click a node to expand"}
        </span>
      </div>
      <EntityDetailPanel onExpand={(id) => void expand(id)} busy={loading} />
    </section>
  );
}

export function GraphCanvas() {
  return (
    <ReactFlowProvider>
      <Canvas />
    </ReactFlowProvider>
  );
}
