import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect, useRef } from "react";
import { Icon } from "../Icon";
import { DecisionTimeline } from "../entities/DecisionTimeline";
import { freshness, useGraphStore } from "../../store/graphStore";
import { safeUrl } from "../../api/safeUrl";
import { CopyButton } from "../CopyButton";
import { colors } from "./colors";

export function EntityDetailPanel({
  onExpand,
  busy = false,
}: {
  onExpand: (id: string) => void;
  busy?: boolean;
}) {
  const { graph, selected, select, expanding, highlight } = useGraphStore();
  const node = graph.nodes.find((n) => n.id === selected);
  const reduced = useReducedMotion();
  const closeButton = useRef<HTMLButtonElement>(null);
  const panel = useRef<HTMLElement>(null);
  function close() {
    select(null);
    if (selected)
      document
        .querySelector<HTMLElement>(`[data-id="${CSS.escape(selected)}"]`)
        ?.focus({ preventScroll: true });
  }
  useEffect(() => {
    if (panel.current) panel.current.scrollTop = 0;
    if (selected && document.documentElement.dataset.input === "keyboard")
      closeButton.current?.focus({ preventScroll: true });
  }, [selected]);
  useEffect(() => {
    if (!selected) return;
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        select(null);
        document
          .querySelector<HTMLElement>(`[data-id="${CSS.escape(selected)}"]`)
          ?.focus();
      }
    };
    window.addEventListener("keydown", escape);
    return () => window.removeEventListener("keydown", escape);
  }, [selected, select]);
  const url = node
    ? safeUrl(node.properties.source_url ?? node.properties.url)
    : undefined;
  const relationships = graph.edges.filter(
    (e) => node && (e.source_id === node.id || e.target_id === node.id),
  );
  const properties = Object.entries(node?.properties ?? {}).filter(
    ([key]) =>
      ![
        "description",
        "source_id",
        "source_type",
        "source_url",
        "url",
        "ingested_at",
        "source_updated_at",
        "content_hash",
        "freshness_status",
      ].includes(key),
  );
  return (
    <AnimatePresence
      initial={false}
      custom={reduced || document.documentElement.dataset.input === "keyboard"}
    >
      {node && (
        <motion.aside
          ref={panel}
          className="entity-detail"
          aria-label="Entity details"
          key="entity-details"
          initial={{
            opacity: 0,
            transform: reduced ? "translateY(0px)" : "translateY(12px)",
          }}
          animate={{ opacity: 1, transform: "translateY(0px)" }}
          variants={{
            closed: (instant: boolean) => ({
              opacity: 0,
              transform: instant ? "translateY(0px)" : "translateY(8px)",
              transition: { duration: instant ? 0 : 0.15 },
            }),
          }}
          exit="closed"
          transition={{
            duration:
              reduced || document.documentElement.dataset.input === "keyboard"
                ? 0
                : 0.2,
            ease: [0.22, 1, 0.36, 1],
          }}
        >
          <button ref={closeButton} className="close" onClick={close}>
            <Icon name="close" size={14} /> Close
          </button>
          <span className="detail-type" style={{ color: colors[node.type] }}>
            <Icon name={node.type} size={16} />
            {node.type}
          </span>
          <h2>{node.title}</h2>
          <div className="detail-identity">
            <code className="detail-id">{node.id}</code>
            <CopyButton
              key={node.id}
              text={node.id}
              label="Copy entity ID"
              compact
            />
          </div>
          {typeof node.properties.description === "string" && (
            <p className="detail-description">{node.properties.description}</p>
          )}
          <div className="detail-actions">
            <button
              className="detail-expand"
              disabled={busy || expanding.has(node.id)}
              onClick={() => onExpand(node.id)}
            >
              <Icon name="plus" size={14} />
              {expanding.has(node.id) ? "Expanding…" : "Expand neighborhood"}
            </button>
            {url && (
              <a
                className="source-link"
                href={url}
                target="_blank"
                rel="noreferrer"
              >
                Open source ↗
              </a>
            )}
          </div>
          <div className="detail-provenance">
            <span className="freshness-badge" data-freshness={freshness(node)}>
              Freshness: {freshness(node)}
            </span>
            <span>
              Source: {String(node.properties.source_type ?? "unknown")}
            </span>
          </div>
          {properties.length > 0 && (
            <>
              <h3>Properties</h3>
              <dl>
                {properties.map(([key, value]) => (
                  <div key={key}>
                    <dt>{key.replaceAll("_", " ")}</dt>
                    <dd>
                      {typeof value === "string"
                        ? value
                        : JSON.stringify(value)}
                    </dd>
                  </div>
                ))}
              </dl>
            </>
          )}
          <details className="source-details">
            <summary>Source details</summary>
            <dl>
              {[
                "source_id",
                "source_type",
                "ingested_at",
                "source_updated_at",
                "content_hash",
              ].map(
                (key) =>
                  node.properties[key] != null && (
                    <div key={key}>
                      <dt>{key.replaceAll("_", " ")}</dt>
                      <dd>{String(node.properties[key])}</dd>
                    </div>
                  ),
              )}
            </dl>
          </details>
          <h3>
            Relationships{" "}
            <span className="count-label">{relationships.length}</span>
          </h3>
          <div className="relationship-list">
            {relationships.map((edge) => {
              const outgoing = edge.source_id === node.id;
              const neighborId = outgoing ? edge.target_id : edge.source_id;
              const neighbor = graph.nodes.find(
                (item) => item.id === neighborId,
              );
              return (
                <button
                  key={edge.id}
                  className="relationship-row"
                  onClick={() => {
                    highlight([neighborId]);
                    select(neighborId);
                  }}
                  title={`${edge.source_id} → ${edge.relationship_type} → ${edge.target_id}`}
                >
                  <Icon
                    name={neighbor?.type ?? "graph"}
                    size={16}
                    style={{
                      color: neighbor ? colors[neighbor.type] : undefined,
                    }}
                  />
                  <span>
                    <strong>{neighbor?.title ?? neighborId}</strong>
                    <small>
                      {outgoing ? "Outgoing ·" : "Incoming ·"}{" "}
                      {edge.relationship_type
                        .replaceAll("_", " ")
                        .toLowerCase()}
                    </small>
                  </span>
                  <Icon name="arrow" size={14} />
                </button>
              );
            })}
            {!relationships.length && (
              <p className="muted">
                No relationships in this view. Expand to explore connected
                records.
              </p>
            )}
          </div>
          {node.type === "service" && <DecisionTimeline serviceId={node.id} />}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
