import { Link } from "react-router-dom";
import type { KnowledgeGaps, GraphNode } from "../../types/api";

export function GapsList({
  gaps,
  onSelect,
}: {
  gaps: KnowledgeGaps;
  onSelect: (node: GraphNode) => void;
}) {
  const groups = [
    ["Unowned services", gaps.unowned_services],
    ["Decisions missing rationale", gaps.decisions_missing_rationale],
    ["Undocumented services", gaps.undocumented_services],
  ] as const;
  return (
    <section className="gaps-list">
      <h2>Knowledge gaps</h2>
      {gaps.warning && <p className="notice">{gaps.warning}</p>}
      {gaps.total_gaps === 0 && <p>No gaps found in the retrieved records.</p>}
      {groups.map(([title, nodes]) => (
        <section key={title}>
          <h3>
            {title} · {nodes.length}
          </h3>
          {nodes.map((node) => (
            <article key={node.id}>
              <button onClick={() => onSelect(node)}>{node.title}</button>
              <code>{node.id}</code>
              {node.type === "service" && (
                <Link
                  to={`/onboarding?service_id=${encodeURIComponent(node.id)}`}
                >
                  Open onboarding ↗
                </Link>
              )}
            </article>
          ))}
        </section>
      ))}
    </section>
  );
}
