import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { getOnboardingBrief } from '../api/reports';

export function OnboardingPage() {
  const [params] = useSearchParams();
  const serviceId = params.get('service_id') ?? 'service:authentication-api';
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getOnboardingBrief(serviceId)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [serviceId]);

  if (loading) {
    return (
      <div style={{ padding: 40, color: 'var(--text-secondary)' }}>
        Building onboarding brief...
      </div>
    );
  }
  if (error || !data) {
    return (
      <div style={{ padding: 40, color: 'var(--stale)' }}>
        Error: {error}
      </div>
    );
  }

  const experts = (data.top_experts as unknown[]) ?? [];
  const decisions = (data.key_decisions as unknown[]) ?? [];

  return (
    <div style={{ maxWidth: 760, margin: '0 auto', padding: 40 }}>
      {/* Header */}
      <div style={{ marginBottom: 32 }}>
        <span
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-muted)',
          }}
        >
          {serviceId}
        </span>
        <h1
          style={{
            margin: '8px 0',
            fontSize: 'var(--text-2xl)',
            color: 'var(--text-primary)',
          }}
        >
          {String(data.service_title ?? serviceId)}
        </h1>
        <p
          style={{
            margin: 0,
            fontSize: 'var(--text-base)',
            lineHeight: 1.6,
            color: 'var(--text-secondary)',
          }}
        >
          {String(data.answer ?? '')}
        </p>
      </div>

      {/* Sections grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: 20,
        }}
      >
        {/* Experts */}
        <Section title="Top Experts" icon="👤">
          {experts.length === 0 ? (
            <p style={muted}>No experts recorded.</p>
          ) : (
            experts.map((e: unknown) => {
              const ex = e as Record<string, string>;
              return (
                <div key={ex.id} style={chipStyle}>
                  <span style={{ color: 'var(--c-person)' }}>●</span>{' '}
                  {ex.name ?? ex.id}
                </div>
              );
            })
          )}
        </Section>

        {/* Blast radius */}
        <Section title="Blast Radius" icon="⚡">
          <p style={{ ...muted, margin: 0 }}>
            {String(data.blast_radius_summary ?? 'Unknown')}
          </p>
        </Section>

        {/* Key decisions */}
        <Section
          title="Key Decisions"
          icon="📋"
          style={{ gridColumn: '1 / -1' }}
        >
          {decisions.length === 0 ? (
            <p style={muted}>No decisions recorded.</p>
          ) : (
            decisions.map((d: unknown) => {
              const dec = d as Record<string, string>;
              return (
                <div
                  key={dec.source_id}
                  style={{
                    padding: '12px 0',
                    borderBottom: '1px solid var(--border)',
                  }}
                >
                  <code
                    style={{
                      fontSize: 'var(--text-xs)',
                      color: 'var(--text-code)',
                    }}
                  >
                    {dec.source_id}
                  </code>
                  <p
                    style={{
                      margin: '4px 0 0',
                      color: 'var(--text-primary)',
                      fontSize: 'var(--text-sm)',
                    }}
                  >
                    {dec.title}
                  </p>
                  {dec.excerpt && (
                    <p style={{ margin: '4px 0 0', ...muted }}>
                      {dec.excerpt}
                    </p>
                  )}
                </div>
              );
            })
          )}
        </Section>
      </div>
    </div>
  );
}

function Section({
  title,
  icon,
  children,
  style,
}: {
  title: string;
  icon: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
}) {
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 10,
        padding: 20,
        ...style,
      }}
    >
      <h3
        style={{
          margin: '0 0 14px',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-secondary)',
          textTransform: 'uppercase',
          letterSpacing: '0.06em',
        }}
      >
        {icon} {title}
      </h3>
      {children}
    </div>
  );
}

const muted: React.CSSProperties = {
  fontSize: 'var(--text-sm)',
  color: 'var(--text-secondary)',
};

const chipStyle: React.CSSProperties = {
  fontSize: 'var(--text-sm)',
  color: 'var(--text-primary)',
  padding: '4px 0',
};
