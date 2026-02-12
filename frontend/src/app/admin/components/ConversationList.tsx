"use client";

import { useState, useEffect } from "react";

interface Conversation {
  session_id: string;
  created_at: string | null;
  last_active: string | null;
  language: string;
  message_count: number;
  last_question: string | null;
}

interface ConversationDetail {
  session_id: string;
  language: string;
  messages: {
    id: number;
    role: string;
    content: string;
    confidence: number | null;
    response_time_ms: number | null;
    created_at: string | null;
    feedback: { rating: number; comment: string | null } | null;
  }[];
}

interface Props {
  adminFetch: (path: string, options?: RequestInit) => Promise<any>;
}

export default function ConversationList({ adminFetch }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadConversations();
  }, [page]);

  const loadConversations = async () => {
    setLoading(true);
    try {
      const data = await adminFetch(`/api/admin/conversations?page=${page}&per_page=10`);
      setConversations(data.conversations || []);
      setTotal(data.total || 0);
    } catch {
      // empty
    } finally {
      setLoading(false);
    }
  };

  const viewConversation = async (sessionId: string) => {
    try {
      const data = await adminFetch(`/api/admin/conversations/${sessionId}`);
      setSelected(data);
    } catch {
      // empty
    }
  };

  const totalPages = Math.ceil(total / 10);

  if (selected) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Conversation Detail</h3>
            <p className="text-xs text-gray-400 mt-0.5">
              Session: {selected.session_id.slice(0, 8)}... | Language: {selected.language || "en"}
            </p>
          </div>
          <button
            onClick={() => setSelected(null)}
            className="text-sm text-blue-600 hover:text-blue-800"
          >
            &larr; Back to list
          </button>
        </div>
        <div className="space-y-3 max-h-96 overflow-y-auto">
          {selected.messages.map((msg) => (
            <div
              key={msg.id}
              className={`p-3 rounded-lg text-sm ${
                msg.role === "user"
                  ? "bg-blue-50 text-blue-900 ml-8"
                  : "bg-gray-50 text-gray-800 mr-8"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-gray-500 uppercase">{msg.role}</span>
                <div className="flex items-center gap-2">
                  {msg.confidence !== null && (
                    <span className="text-xs text-gray-400">
                      {Math.round(msg.confidence * 100)}% conf
                    </span>
                  )}
                  {msg.response_time_ms !== null && (
                    <span className="text-xs text-gray-400">
                      {(msg.response_time_ms / 1000).toFixed(1)}s
                    </span>
                  )}
                  {msg.feedback && (
                    <span className={`text-xs ${msg.feedback.rating === 1 ? "text-green-600" : "text-red-600"}`}>
                      {msg.feedback.rating === 1 ? "+" : "-"}1
                    </span>
                  )}
                </div>
              </div>
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">
        Recent Conversations ({total})
      </h3>
      {loading ? (
        <p className="text-sm text-gray-400 py-4 text-center">Loading...</p>
      ) : conversations.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">No conversations yet</p>
      ) : (
        <>
          <div className="space-y-2">
            {conversations.map((c) => (
              <button
                key={c.session_id}
                onClick={() => viewConversation(c.session_id)}
                className="w-full text-left p-3 rounded-lg border border-gray-100 hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <p className="text-sm text-gray-700 line-clamp-1 flex-1">
                    {c.last_question || "No messages"}
                  </p>
                  <span className="text-xs text-gray-400 ml-3 flex-shrink-0">
                    {c.message_count} msgs
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-xs text-gray-400">
                    {c.last_active ? new Date(c.last_active).toLocaleString() : "—"}
                  </span>
                  <span className="text-xs text-gray-400 uppercase">{c.language || "en"}</span>
                </div>
              </button>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-4 pt-3 border-t border-gray-100">
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
        </>
      )}
    </div>
  );
}
