"use client";

import { useState, useEffect } from "react";

interface AuditEntry {
  id: number;
  timestamp: string | null;
  action: string;
  session_id: string | null;
  user_input: string | null;
  retrieved_chunks: { title: string; url: string; distance: number }[] | null;
  response_preview: string | null;
  confidence: number | null;
  topic: string | null;
  metadata: Record<string, any> | null;
}

interface Props {
  adminFetch: (path: string, options?: RequestInit) => Promise<any>;
}

const ACTION_LABELS: Record<string, string> = {
  chat_query: "Chat Query",
  document_uploaded: "Doc Upload",
  crawl_started: "Crawl Start",
  crawl_completed: "Crawl Done",
  admin_action: "Admin",
  feedback_received: "Feedback",
  cache_cleared: "Cache Clear",
};

export default function AuditLog({ adminFetch }: Props) {
  const [logs, setLogs] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadLogs();
  }, [page, filter]);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const actionParam = filter ? `&action=${filter}` : "";
      const data = await adminFetch(
        `/api/admin/audit-logs?days=30&page=${page}&per_page=20${actionParam}`
      );
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch {
      // empty
    } finally {
      setLoading(false);
    }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">Audit Log ({total})</h3>
        <select
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setPage(1); }}
          className="text-xs border border-gray-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="">All actions</option>
          <option value="chat_query">Chat queries</option>
          <option value="document_uploaded">Document uploads</option>
          <option value="feedback_received">Feedback</option>
          <option value="admin_action">Admin actions</option>
        </select>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400 py-4 text-center">Loading...</p>
      ) : logs.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">No audit entries</p>
      ) : (
        <div className="space-y-1 max-h-96 overflow-y-auto">
          {logs.map((log) => (
            <div key={log.id}>
              <button
                onClick={() => setExpanded(expanded === log.id ? null : log.id)}
                className="w-full text-left p-2.5 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded flex-shrink-0">
                    {ACTION_LABELS[log.action] || log.action}
                  </span>
                  <span className="text-sm text-gray-700 truncate flex-1">
                    {log.user_input || log.metadata?.filename || "—"}
                  </span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {log.confidence !== null && (
                      <span className="text-xs text-gray-400">
                        {Math.round(log.confidence * 100)}%
                      </span>
                    )}
                    {log.topic && log.topic !== "general" && (
                      <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                        {log.topic}
                      </span>
                    )}
                    <span className="text-xs text-gray-300">
                      {log.timestamp ? new Date(log.timestamp).toLocaleString() : ""}
                    </span>
                  </div>
                </div>
              </button>

              {expanded === log.id && (
                <div className="ml-4 p-3 bg-gray-50 rounded-lg text-xs space-y-2 mb-2">
                  {log.response_preview && (
                    <div>
                      <span className="font-medium text-gray-500">Response: </span>
                      <span className="text-gray-700">{log.response_preview}</span>
                    </div>
                  )}
                  {log.retrieved_chunks && log.retrieved_chunks.length > 0 && (
                    <div>
                      <span className="font-medium text-gray-500">Retrieved chunks:</span>
                      <div className="mt-1 space-y-1">
                        {log.retrieved_chunks.map((chunk, i) => (
                          <div key={i} className="flex items-center gap-2">
                            <span className="text-gray-600">{chunk.title}</span>
                            <span className="text-gray-400">
                              (dist: {chunk.distance.toFixed(3)})
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {log.metadata && (
                    <div>
                      <span className="font-medium text-gray-500">Metadata: </span>
                      <span className="text-gray-600 font-mono">
                        {JSON.stringify(log.metadata)}
                      </span>
                    </div>
                  )}
                  {log.session_id && (
                    <div>
                      <span className="font-medium text-gray-500">Session: </span>
                      <span className="text-gray-600 font-mono">{log.session_id.slice(0, 12)}...</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-100">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-300"
          >
            Previous
          </button>
          <span className="text-xs text-gray-500">
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-300"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
