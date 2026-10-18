import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useEffect } from "react";
import { Icon } from "../Icon";
import { DecisionTimeline } from "../entities/DecisionTimeline";
import { freshness, useGraphStore } from "../../store/graphStore";
import { safeUrl } from "../../api/safeUrl";

export function EntityDetailPanel() {
  const { graph, selected, select } = useGraphStore();
  const node = graph.nodes.find((n) => n.id === selected);
  const reduced = useReducedMotion();
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
  return (
    <AnimatePresence
      initial={false}
      custom={reduced || document.documentElement.dataset.input === "keyboard"}
    >
      {node && (
        <motion.aside
          className="entity-detail"
          aria-label="Entity details"
          key={node.id}
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
          <button className="close" onClick={() => select(null)}>
            Close
          </button>
          <span className="detail-type">
            <Icon name={node.type} size={16} />
            {node.type}
          </span>
          <h2>{node.title}</h2>
          <code>{node.id}</code>
          <p>Freshness: {freshness(node)}</p>
          <p>Source ID: {String(node.properties.source_id ?? "unknown")}</p>
          <p>Source type: {String(node.properties.source_type ?? "unknown")}</p>
          {url && (
            <a href={url} target="_blank" rel="noreferrer">
              Open source ↗
            </a>
          )}
          <h3>Properties</h3>
          <dl>
            {Object.entries(node.properties).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>
                  {typeof value === "string" ? value : JSON.stringify(value)}
                </dd>
              </div>
            ))}
          </dl>
          <h3>Relationships ({relationships.length})</h3>
          {relationships.map((e) => (
            <p key={e.id}>
              <code>{e.source_id}</code> →{" "}
              <strong>{e.relationship_type}</strong> →{" "}
              <code>{e.target_id}</code>
            </p>
          ))}
          {node.type === "service" && <DecisionTimeline serviceId={node.id} />}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
