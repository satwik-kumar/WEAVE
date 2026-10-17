import type { HealthReport } from "../../types/api";

const labels: Record<string, string> = {
  services_owned: "Services owned",
  decisions_rationale: "Decisions with rationale",
  incidents_resolved: "Incidents resolved",
  services_documented: "Services documented",
};
export function HealthScorePanel({ report }: { report: HealthReport }) {
  return (
    <section aria-label="Knowledge health score">
      <div className="health-score">
        <strong>
          {report.health_score}
          <small>/100</small>
        </strong>
        <div>
          <h2>Knowledge health</h2>
          <p>
            {report.gaps.total_gaps} gaps across ownership, rationale and
            documentation
          </p>
        </div>
      </div>
      <div className="metric-grid">
        {Object.entries(report.metrics).map(([key, value]) => (
          <article key={key}>
            <strong>{Math.round(value * 100)}%</strong>
            <span>{labels[key] ?? key}</span>
            <progress aria-label={labels[key]} max={1} value={value} />
          </article>
        ))}
      </div>
    </section>
  );
}
