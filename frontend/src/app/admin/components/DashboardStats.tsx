"use client";

interface Summary {
  total_sessions: number;
  total_questions: number;
  avg_response_time_ms: number | null;
  avg_confidence: number | null;
  feedback_positive: number;
  feedback_negative: number;
  satisfaction_rate: number | null;
}

interface Props {
  summary: Summary | null;
}

function StatCard({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <p className="text-sm text-gray-500 mb-1">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  );
}

export default function DashboardStats({ summary }: Props) {
  if (!summary) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse">
            <div className="h-4 w-20 bg-gray-200 rounded mb-2" />
            <div className="h-8 w-16 bg-gray-200 rounded" />
          </div>
        ))}
      </div>
    );
  }

  const avgTime = summary.avg_response_time_ms
    ? `${(summary.avg_response_time_ms / 1000).toFixed(1)}s`
    : "—";

  const avgConf = summary.avg_confidence
    ? `${Math.round(summary.avg_confidence * 100)}%`
    : "—";

  const satisfaction = summary.satisfaction_rate !== null
    ? `${summary.satisfaction_rate}%`
    : "—";

  const totalFeedback = summary.feedback_positive + summary.feedback_negative;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard label="Sessions" value={summary.total_sessions.toLocaleString()} />
      <StatCard label="Questions" value={summary.total_questions.toLocaleString()} />
      <StatCard label="Avg Response Time" value={avgTime} />
      <StatCard
        label="Avg Confidence"
        value={avgConf}
      />
      <StatCard
        label="Satisfaction"
        value={satisfaction}
        sub={totalFeedback > 0 ? `${totalFeedback} ratings` : undefined}
      />
      <StatCard label="Positive Feedback" value={summary.feedback_positive.toLocaleString()} />
      <StatCard label="Negative Feedback" value={summary.feedback_negative.toLocaleString()} />
    </div>
  );
}
