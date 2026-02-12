"use client";

interface UnansweredQuestion {
  question: string;
  confidence: number;
  created_at: string | null;
  session_id: string;
}

interface Props {
  questions: UnansweredQuestion[];
}

export default function UnansweredQuestions({ questions }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-1">Low-Confidence Questions</h3>
      <p className="text-xs text-gray-400 mb-4">Questions the bot struggled to answer</p>
      {questions.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">No low-confidence answers</p>
      ) : (
        <div className="space-y-2 max-h-80 overflow-y-auto">
          {questions.map((q, i) => (
            <div key={i} className="py-2 border-b border-gray-100 last:border-0">
              <p className="text-sm text-gray-700 line-clamp-2">{q.question}</p>
              <div className="flex items-center gap-3 mt-1">
                <span className="text-xs text-amber-600 font-medium">
                  {Math.round(q.confidence * 100)}% confidence
                </span>
                {q.created_at && (
                  <span className="text-xs text-gray-400">
                    {new Date(q.created_at).toLocaleDateString()}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
