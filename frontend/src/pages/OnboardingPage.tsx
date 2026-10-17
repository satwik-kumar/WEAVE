import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { getOnboardingBrief } from "../api/reports";
import { searchEntities } from "../api/graph";
import { EvidenceList } from "../components/chat/EvidenceList";
import { DecisionTimeline } from "../components/entities/DecisionTimeline";
import { GraphCanvas } from "../components/graph/GraphCanvas";
import { useGraphStore } from "../store/graphStore";

export function OnboardingPage() {
  useEffect(() => {
    useGraphStore.getState().setContext("onboarding");
  }, []);
  const [params, setParams] = useSearchParams();
  const service = params.get("service_id") || "service:authentication-api";
  const { data: entities = [], error: serviceFailure } = useQuery({
    queryKey: ["services"],
    queryFn: () => searchEntities("service:"),
  });
  const services = entities.filter((n) => n.type === "service");
  const {
    data: brief,
    error: failure,
    isFetching: loading,
    refetch,
  } = useQuery({
    queryKey: ["onboarding", service],
    queryFn: () => getOnboardingBrief(service),
  });
  const error = failure?.message;
  useEffect(() => {
    if (brief) useGraphStore.getState().replace(brief.graph);
  }, [brief]);
  return (
    <main className="report-workspace">
      <section className="report-content">
        <div className="panel-heading">
          <div>
            <small>START WITH CONTEXT</small>
            <h1>Service Onboarding</h1>
          </div>
        </div>
        {serviceFailure && (
          <p className="notice">
            Service list unavailable: {serviceFailure.message}
          </p>
        )}
        <label className="service-picker">
          Service
          <select
            aria-label="Choose service"
            value={service}
            onChange={(e) => setParams({ service_id: e.target.value })}
          >
            {!services.some((n) => n.id === service) && (
              <option value={service}>{service}</option>
            )}
            {services.map((node) => (
              <option key={node.id} value={node.id}>
                {node.title}
              </option>
            ))}
          </select>
        </label>
        {loading && <p role="status">Building onboarding brief…</p>}
        {error && (
          <p role="alert" className="error">
            {error}
            <button onClick={() => void refetch()}>Retry onboarding</button>
          </p>
        )}
        {brief && !loading && !error && (
          <article>
            <h2>{brief.service_title}</h2>
            <p>{brief.overview}</p>
            {brief.warnings.map((w) => (
              <p className="notice" key={w}>
                {w}
              </p>
            ))}
            <h3>People to talk to</h3>
            {brief.top_experts.length ? (
              brief.top_experts.map((n) => (
                <p key={n.id}>
                  <strong>{n.title}</strong> <code>{n.id}</code>
                </p>
              ))
            ) : (
              <p>No experts recorded.</p>
            )}
            <h3>Change risks</h3>
            {brief.change_risks.length ? (
              <ul>
                {brief.change_risks.map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
            ) : (
              <p>No dependent services retrieved.</p>
            )}
            <h3>Open incidents</h3>
            {brief.open_incidents.length ? (
              brief.open_incidents.map((n) => <p key={n.id}>{n.title}</p>)
            ) : (
              <p>No open incidents retrieved.</p>
            )}
            <h3>Related tickets</h3>
            {brief.related_tickets.length ? (
              brief.related_tickets.map((n) => (
                <p key={n.id}>
                  {n.title} · {String(n.properties.status ?? "unknown")}
                </p>
              ))
            ) : (
              <p>No tickets retrieved.</p>
            )}
            <h3>Current decisions</h3>
            <EvidenceList evidence={brief.key_decisions} graph={brief.graph} />
            <DecisionTimeline serviceId={brief.service_id} />
          </article>
        )}
      </section>
      <GraphCanvas />
    </main>
  );
}
