import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { getHealthReport } from "../api/reports";
import { getNeighborhood } from "../api/graph";
import type { GraphNode } from "../types/api";
import { HealthScorePanel } from "../components/health/HealthScorePanel";
import { GapsList } from "../components/health/GapsList";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { useGraphStore } from "../store/graphStore";

export function HealthPage() {
  const {
    data: report,
    error: failure,
    refetch,
    isFetching,
  } = useQuery({ queryKey: ["health"], queryFn: getHealthReport });
  const [expansionError, setExpansionError] = useState("");
  const [expanding, setExpanding] = useState(false);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    useGraphStore.getState().setContext("health");
    return () => {
      active.current = false;
    };
  }, []);
  const error = expansionError || failure?.message;
  useEffect(() => {
    if (report) useGraphStore.getState().replace(report.graph);
  }, [report]);
  async function select(node: GraphNode) {
    if (expanding) return;
    setExpanding(true);
    try {
      const graph = await getNeighborhood(node.id);
      if (!active.current) return;
      useGraphStore.getState().replace(graph);
      useGraphStore.getState().select(node.id);
    } catch (e) {
      if (active.current)
        setExpansionError(
          e instanceof Error ? e.message : "Gap expansion failed.",
        );
    } finally {
      if (active.current) setExpanding(false);
    }
  }
  return (
    <main className="report-workspace">
      <section className="report-content">
        <div className="panel-heading">
          <div>
            <small>FIND THE MISSING CONTEXT</small>
            <h1>Knowledge Health</h1>
          </div>
          <button disabled={isFetching} aria-busy={isFetching} onClick={() => void refetch()}>Refresh</button>
        </div>
        {error && (
          <p role="alert" className="error">
            {error}
            <button onClick={() => void refetch()}>Retry report</button>
          </p>
        )}
        {isFetching && !error && <p role="status">Loading knowledge health…</p>}
        {report && (
          <>
            <HealthScorePanel report={report} />
            {report.warnings.map((w) => (
              <p className="notice" key={w}>
                {w}
              </p>
            ))}
            <GapsList
              gaps={report.gaps}
              onSelect={(node) => void select(node)}
            />
          </>
        )}
        {expanding && <p role="status">Loading gap context…</p>}
      </section>
      <GraphCanvas />
    </main>
  );
}
