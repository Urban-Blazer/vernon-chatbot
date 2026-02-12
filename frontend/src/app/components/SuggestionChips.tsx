"use client";

interface Suggestion {
  text: string;
  query: string;
}

interface SuggestionChipsProps {
  suggestions: Suggestion[];
  onSelect: (query: string) => void;
  visible: boolean;
}

export default function SuggestionChips({
  suggestions,
  onSelect,
  visible,
}: SuggestionChipsProps) {
  if (!visible || suggestions.length === 0) return null;

  return (
    <div
      className="flex flex-wrap gap-2 px-4 py-2"
      role="group"
      aria-label="Suggested questions"
    >
      {suggestions.map((s, i) => (
        <button
          key={i}
          onClick={() => onSelect(s.query)}
          className="text-xs px-3 py-1.5 rounded-full border border-blue-200 text-blue-700
                     hover:bg-blue-50 hover:border-blue-300 transition-colors
                     focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-1"
        >
          {s.text}
        </button>
      ))}
    </div>
  );
}
