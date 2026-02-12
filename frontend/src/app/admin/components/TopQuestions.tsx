"use client";

interface Question {
  question: string;
  count: number;
}

interface Props {
  questions: Question[];
}

export default function TopQuestions({ questions }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Top Questions</h3>
      {questions.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">No data yet</p>
      ) : (
        <div className="space-y-2">
          {questions.map((q, i) => (
            <div key={i} className="flex items-start justify-between gap-3 py-2 border-b border-gray-100 last:border-0">
              <p className="text-sm text-gray-700 line-clamp-2 flex-1">{q.question}</p>
              <span className="text-xs font-medium text-gray-500 bg-gray-100 rounded-full px-2 py-0.5 flex-shrink-0">
                {q.count}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
