import type { KnowledgeGap } from '../../types/api';

const GAP_LABEL: Record<string, string> = {
  no_owner: 'No owner assigned',
  missing_rationale: 'Decision has no documented rationale',
  undocumented: 'No linked documentation',
};

export function GapsList({ gaps }: { gaps: KnowledgeGap[] }) {
  if (!gaps.length) {
    return (
      <p style={{ color: 'var(--text-secondary)', fontSize: 'var(--text-sm)' }}>
        No knowledge gaps found. Graph is complete.
      </p>
    );
  }
  return (
    <div>
      <h3
        style={{
          fontSize: 'var(--text-base)',
          color: 'var(--text-primary)',
          marginBottom: 12,
        }}
      >
        Knowledge Gaps
      </h3>
      {gaps.map((g) => (
        <div
          key={g.entity_id}
          style={{
            display: 'flex',
            gap: 12,
            alignItems: 'flex-start',
            padding: '10px 0',
            borderBottom: '1px solid var(--border)',
          }}
        >
          <span style={{ color: 'var(--aging)', marginTop: 1 }}>▲</span>
          <div>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                color: 'var(--text-code)',
              }}
            >
              {g.entity_id}
            </span>
            <p
              style={{
                margin: '2px 0 0',
                fontSize: 'var(--text-sm)',
                color: 'var(--text-secondary)',
              }}
            >
              {GAP_LABEL[g.gap_type] ?? g.gap_type}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
