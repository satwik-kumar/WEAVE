import { useEffect, useState } from 'react';

interface TimelineItem {
  id: string;
  title: string;
  status: string; // "active" | "superseded"
  decision_date?: string;
  rationale?: string;
}

async function fetchDecisions(serviceId: string): Promise<TimelineItem[]> {
  try {
    const res = await fetch(
      `/api/v1/reports/onboarding?service_id=${encodeURIComponent(serviceId)}`
    );
    if (!res.ok) return [];
    const data = await res.json();
    const raw = (data.key_decisions ?? []) as Array<Record<string, unknown>>;
    return raw.map((d) => ({
      id: String(d.id || d.source_id || ''),
      title: String(d.title || ''),
      status: String(d.status || d.decision_status || 'active'),
      decision_date: d.decision_date ? String(d.decision_date) : undefined,
      rationale:
        d.rationale || d.excerpt ? String(d.rationale || d.excerpt) : undefined,
    }));
  } catch {
    return [];
  }
}

export function DecisionTimeline({ serviceId }: { serviceId: string }) {
  const [items, setItems] = useState<TimelineItem[]>([]);

  useEffect(() => {
    fetchDecisions(serviceId).then(setItems);
  }, [serviceId]);

  if (!items.length) return null;

  return (
    <div style={{ marginTop: 16 }}>
      <h4
        style={{
          fontSize: 'var(--text-xs)',
          color: 'var(--text-muted)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
          margin: '0 0 10px',
        }}
      >
        Decision History
      </h4>
      {items.map((item) => (
        <div
          key={item.id}
          style={{
            padding: '8px 0',
            borderLeft: '2px solid var(--c-decision)',
            paddingLeft: 12,
            marginBottom: 8,
            opacity: item.status === 'superseded' ? 0.45 : 1,
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              color: 'var(--text-code)',
              textDecoration:
                item.status === 'superseded' ? 'line-through' : 'none',
            }}
          >
            {item.id}
          </span>
          <p
            style={{
              margin: '2px 0 0',
              fontSize: 'var(--text-sm)',
              color: 'var(--text-primary)',
            }}
          >
            {item.title}
            {item.status === 'superseded' && (
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 'var(--text-xs)',
                  color: 'var(--stale)',
                }}
              >
                superseded
              </span>
            )}
          </p>
        </div>
      ))}
    </div>
  );
}
