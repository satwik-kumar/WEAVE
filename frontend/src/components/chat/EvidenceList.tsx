import { Icon } from "../Icon";
import type { EvidenceItem, GraphView } from "../../types/api";
import { useGraphStore } from "../../store/graphStore";
import { safeUrl } from "../../api/safeUrl";

const sourceTypeIcon: Record<string, string> = {
  decision: "decision",
  incident: "incident",
  ticket: "ticket",
  service: "service",
  team: "team",
  person: "person",
  repository: "repository",
  github: "repository",
  file: "file",
  yaml: "file",
  json: "file",
  test: "test",
  project: "project",
};

export function EvidenceList({
  evidence,
  graph,
}: {
  evidence: EvidenceItem[];
  graph?: GraphView | null;
}) {
  const highlight = useGraphStore((s) => s.highlight);
  const focus = (ids: string[]) => {
    if (graph) useGraphStore.getState().replace(graph);
    highlight(ids);
  };
  if (!evidence.length)
    return <p className="muted">No evidence items were returned.</p>;
  return (
    <details className="evidence" open>
      <summary>
        <h3>
          Sources <span className="count-label">{evidence.length}</span>
        </h3>
        <span className="sources-hint">Supporting records</span>
      </summary>
      {evidence.map((item, i) => (
        <article key={`${item.source_id}-${i}`}>
          <div className="evidence-title">
            <span className="source-number">
              {String(i + 1).padStart(2, "0")}
            </span>
            <Icon
              name={sourceTypeIcon[item.source_type] ?? "document"}
              size={15}
            />
            <strong>{item.title}</strong>
          </div>
          <small>
            {item.source_type} · {item.source_id}
          </small>
          {item.excerpt && <p>{item.excerpt}</p>}
          <div>
            {safeUrl(item.source_url) && (
              <a
                href={safeUrl(item.source_url)}
                target="_blank"
                rel="noreferrer"
              >
                Open source ↗
              </a>
            )}{" "}
            {item.relationship_path?.length > 0 && (
              <button onClick={() => focus(item.relationship_path)}>
                Focus evidence path
              </button>
            )}
          </div>
        </article>
      ))}
    </details>
  );
}
