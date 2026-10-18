import { useQuery } from "@tanstack/react-query";
import { getDecisions } from "../../api/reports";
import { useGraphStore } from "../../store/graphStore";

export function DecisionTimeline({ serviceId }: { serviceId: string }) {
  const {
    data: report,
    error: failure,
    refetch,
  } = useQuery({
    queryKey: ["decisions", serviceId],
    queryFn: () => getDecisions(serviceId),
    staleTime: 60_000,
  });
  const error = failure?.message;
  return (
    <section className="decision-timeline" aria-label="Decision timeline">
      <h3>Decision timeline</h3>
      {error ? (
        <p className="error">
          {error}
          <button onClick={() => void refetch()}>Retry timeline</button>
        </p>
      ) : !report ? (
        <p role="status">Loading decisions…</p>
      ) : !report.nodes.length ? (
        <p className="muted">No decisions recorded for this service.</p>
      ) : (
        <ol>
          {report.nodes.map((node) => (
            <li key={node.id}>
              <time>
                {String(node.properties.decision_date ?? "Date unknown")}
              </time>
              <strong>{node.title}</strong>
              <small>
                {String(node.properties.status ?? "Status unknown")}
              </small>
              <p>
                {String(node.properties.rationale || "No rationale recorded.")}
              </p>
              <button
                onClick={() => {
                  useGraphStore
                    .getState()
                    .replace(report.graph, "decision_rationale");
                  useGraphStore.getState().select(node.id);
                }}
              >
                Show decision graph
              </button>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
