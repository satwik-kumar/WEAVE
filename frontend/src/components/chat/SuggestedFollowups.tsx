export function SuggestedFollowups({
  suggestions,
  onSelect,
  disabled = false,
}: {
  suggestions: string[];
  onSelect: (question: string) => void;
  disabled?: boolean;
}) {
  if (!suggestions.length) return null;
  return (
    <section className="followups" aria-label="Suggested followups">
      <h3>Keep exploring</h3>
      {suggestions.map((question) => (
        <button
          disabled={disabled}
          key={question}
          onClick={() => onSelect(question)}
        >
          {question} ↗
        </button>
      ))}
    </section>
  );
}
