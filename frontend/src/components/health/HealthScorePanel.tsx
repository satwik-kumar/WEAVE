import type { HealthScore, HealthDimension } from '../../types/api';

function DimensionRow({ dim }: { dim: HealthDimension }) {
  const pct = Math.round(dim.score * 100);
  const color =
    dim.status === 'good'
      ? 'var(--fresh)'
      : dim.status === 'warning'
      ? 'var(--aging)'
      : 'var(--stale)';
  const icon = dim.status === 'good' ? '✓' : '▲';

  return (
    <div style={{ marginBottom: 12 }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          fontSize: 'var(--text-sm)',
          color: 'var(--text-secondary)',
          marginBottom: 4,
        }}
      >
        <span>{dim.label}</span>
        <span style={{ color }}>
          {dim.current}/{dim.total} &nbsp; {icon}
        </span>
      </div>
      <div
        style={{
          background: 'var(--bg-elevated)',
          borderRadius: 4,
          height: 6,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: '100%',
            background: color,
            borderRadius: 4,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
    </div>
  );
}

export function HealthScorePanel({ data }: { data: HealthScore }) {
  const pct = Math.round(data.overall * 100);
  return (
    <div
      style={{
        background: 'var(--bg-surface)',
        border: '1px solid var(--border)',
        borderRadius: 12,
        padding: 24,
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 20,
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: 'var(--text-lg)',
            color: 'var(--text-primary)',
          }}
        >
          Company Knowledge Health
        </h2>
        <span
          style={{
            fontSize: 'var(--text-2x1)',
            fontWeight: 600,
            color:
              pct >= 80
                ? 'var(--fresh)'
                : pct >= 50
                ? 'var(--aging)'
                : 'var(--stale)',
          }}
        >
          {pct}%
        </span>
      </div>
      {data.dimensions.map((d) => (
        <DimensionRow key={d.label} dim={d} />
      ))}
    </div>
  );
}
