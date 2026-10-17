interface Props {
  suggestions: string[];
  onSelect: (question: string) => void;
}

export function SuggestedFollowups({ suggestions, onSelect }: Props) {
  if (!suggestions || suggestions.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14 }}>
      {suggestions.map((s) => (
        <button
          key={s}
          onClick={() => onSelect(s)}
          style={{
            background: 'var(--bg-elevated)',
            border: '1px solid var(--border)',
            borderRadius: 20,
            padding: '6px 14px',
            fontSize: 'var(--text-xs)',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            transition: 'border-color 0.15s, color 0.15s',
          }}
          onMouseOver={(e) => {
            (e.target as HTMLButtonElement).style.borderColor = 'var(--accent)';
            (e.target as HTMLButtonElement).style.color = 'var(--text-primary)';
          }}
          onMouseOut={(e) => {
            (e.target as HTMLButtonElement).style.borderColor = 'var(--border)';
            (e.target as HTMLButtonElement).style.color =
              'var(--text-secondary)';
          }}
        >
          {s}
        </button>
      ))}
    </div>
  );
}
