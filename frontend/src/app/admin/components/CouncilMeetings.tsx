"use client";

import { useState, useEffect, useCallback } from "react";

interface Meeting {
  id: number;
  escribe_id: string;
  title: string;
  meeting_type: string;
  meeting_date: string | null;
  status: string;
  has_video: boolean;
  has_transcription: boolean;
  has_summary: boolean;
  error_message: string | null;
  processing_started_at: string | null;
  processing_completed_at: string | null;
}

interface MeetingDetail {
  id: number;
  title: string;
  meeting_type: string;
  meeting_date: string | null;
  video_url: string | null;
  status: string;
  executive_summary: string | null;
  action_items: ActionItem[] | null;
  transcription_preview: string | null;
  transcription_length: number;
  error_message: string | null;
}

interface ActionItem {
  description: string;
  assigned_to: string | null;
  deadline: string | null;
  motion_number: string | null;
  status: string;
}

interface ProcessingStatus {
  is_running: boolean;
  current_meeting: string | null;
  total_meetings: number;
  processed: number;
  failed: number;
  current_step: string | null;
  started_at: string | null;
  errors: string[];
}

interface Props {
  adminFetch: (path: string, options?: RequestInit) => Promise<any>;
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-100 text-gray-600",
  downloading: "bg-blue-100 text-blue-700",
  transcribing: "bg-yellow-100 text-yellow-700",
  summarizing: "bg-purple-100 text-purple-700",
  indexing: "bg-indigo-100 text-indigo-700",
  complete: "bg-green-100 text-green-700",
  error: "bg-red-100 text-red-700",
};

const STEP_LABELS: Record<string, string> = {
  discovering: "Discovering meetings...",
  downloading: "Downloading audio...",
  transcribing: "Transcribing audio...",
  summarizing: "Generating summary...",
  indexing: "Indexing in knowledge base...",
  starting: "Starting...",
};

export default function CouncilMeetings({ adminFetch }: Props) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const [detail, setDetail] = useState<MeetingDetail | null>(null);
  const [processing, setProcessing] = useState<ProcessingStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  const loadMeetings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ page: String(page), per_page: "20" });
      if (statusFilter) params.set("status", statusFilter);
      const data = await adminFetch(`/api/admin/meetings?${params}`);
      setMeetings(data.meetings || []);
      setTotal(data.total || 0);
    } catch {
      // empty
    } finally {
      setLoading(false);
    }
  }, [adminFetch, page, statusFilter]);

  const loadStatus = useCallback(async () => {
    try {
      const data = await adminFetch("/api/admin/meetings/processing-status");
      setProcessing(data);
    } catch {
      // empty
    }
  }, [adminFetch]);

  useEffect(() => {
    loadMeetings();
    loadStatus();
  }, [loadMeetings, loadStatus]);

  // Poll processing status when active
  useEffect(() => {
    if (!processing?.is_running) return;
    const interval = setInterval(() => {
      loadStatus();
      loadMeetings();
    }, 5000);
    return () => clearInterval(interval);
  }, [processing?.is_running, loadStatus, loadMeetings]);

  const discover = async () => {
    setMessage("");
    try {
      const data = await adminFetch("/api/admin/meetings/discover", { method: "POST" });
      setMessage(`Discovered ${data.total_discovered} meetings (${data.new_added} new, ${data.with_video} with video)`);
      loadMeetings();
    } catch (e) {
      setMessage("Discovery failed");
    }
  };

  const processAll = async () => {
    setMessage("");
    try {
      await adminFetch("/api/admin/meetings/process-all", { method: "POST" });
      setMessage("Processing started in background");
      loadStatus();
    } catch (e) {
      setMessage("Failed to start processing (may already be running)");
    }
  };

  const processSingle = async (id: number) => {
    try {
      await adminFetch(`/api/admin/meetings/${id}/process`, { method: "POST" });
      setMessage("Processing started");
      loadStatus();
    } catch {
      setMessage("Failed to start processing");
    }
  };

  const toggleExpand = async (id: number) => {
    if (expanded === id) {
      setExpanded(null);
      setDetail(null);
      return;
    }
    setExpanded(id);
    try {
      const data = await adminFetch(`/api/admin/meetings/${id}`);
      setDetail(data);
    } catch {
      setDetail(null);
    }
  };

  const totalPages = Math.ceil(total / 20);

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-900">Council Meetings ({total})</h3>
        <div className="flex items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="text-xs border border-gray-300 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="complete">Complete</option>
            <option value="error">Error</option>
          </select>
          <button
            onClick={discover}
            disabled={processing?.is_running}
            className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            Discover
          </button>
          <button
            onClick={processAll}
            disabled={processing?.is_running}
            className="text-xs px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            Process All
          </button>
        </div>
      </div>

      {/* Processing status bar */}
      {processing?.is_running && (
        <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-center justify-between mb-1">
            <span className="text-xs font-medium text-blue-700">
              {STEP_LABELS[processing.current_step || ""] || "Processing..."}
            </span>
            <span className="text-xs text-blue-600">
              {processing.processed + processing.failed} / {processing.total_meetings}
            </span>
          </div>
          {processing.current_meeting && (
            <p className="text-xs text-blue-600 truncate">{processing.current_meeting}</p>
          )}
          {processing.total_meetings > 0 && (
            <div className="mt-2 h-1.5 bg-blue-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all"
                style={{
                  width: `${((processing.processed + processing.failed) / processing.total_meetings) * 100}%`,
                }}
              />
            </div>
          )}
          {processing.failed > 0 && (
            <p className="text-xs text-red-600 mt-1">{processing.failed} failed</p>
          )}
        </div>
      )}

      {message && (
        <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded mb-3">{message}</p>
      )}

      {loading && meetings.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">Loading...</p>
      ) : meetings.length === 0 ? (
        <p className="text-sm text-gray-400 py-4 text-center">
          No meetings discovered yet. Click &quot;Discover&quot; to scan the eScribe portal.
        </p>
      ) : (
        <div className="space-y-1 max-h-[500px] overflow-y-auto">
          {meetings.map((meeting) => (
            <div key={meeting.id}>
              <button
                onClick={() => toggleExpand(meeting.id)}
                className="w-full text-left p-2.5 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-medium px-1.5 py-0.5 rounded flex-shrink-0 ${STATUS_STYLES[meeting.status] || STATUS_STYLES.pending}`}>
                    {meeting.status}
                  </span>
                  <span className="text-sm text-gray-700 truncate flex-1">
                    {meeting.title}
                  </span>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className="text-xs text-gray-400 bg-gray-100 px-1.5 py-0.5 rounded">
                      {meeting.meeting_type}
                    </span>
                    <span className="text-xs text-gray-300">
                      {meeting.meeting_date
                        ? new Date(meeting.meeting_date).toLocaleDateString()
                        : ""}
                    </span>
                    {meeting.status === "pending" && meeting.has_video && !processing?.is_running && (
                      <button
                        onClick={(e) => { e.stopPropagation(); processSingle(meeting.id); }}
                        className="text-xs text-blue-600 hover:text-blue-800"
                      >
                        Process
                      </button>
                    )}
                    {meeting.status === "error" && !processing?.is_running && (
                      <button
                        onClick={(e) => { e.stopPropagation(); processSingle(meeting.id); }}
                        className="text-xs text-orange-600 hover:text-orange-800"
                      >
                        Retry
                      </button>
                    )}
                  </div>
                </div>
              </button>

              {expanded === meeting.id && detail && detail.id === meeting.id && (
                <div className="ml-4 p-3 bg-gray-50 rounded-lg text-xs space-y-3 mb-2">
                  {detail.error_message && (
                    <div className="p-2 bg-red-50 border border-red-200 rounded">
                      <span className="font-medium text-red-600">Error: </span>
                      <span className="text-red-700">{detail.error_message}</span>
                    </div>
                  )}

                  {detail.executive_summary && (
                    <div>
                      <span className="font-semibold text-gray-700 block mb-1">Executive Summary</span>
                      <div className="text-gray-600 whitespace-pre-wrap leading-relaxed">
                        {detail.executive_summary}
                      </div>
                    </div>
                  )}

                  {detail.action_items && detail.action_items.length > 0 && (
                    <div>
                      <span className="font-semibold text-gray-700 block mb-1">
                        Action Items ({detail.action_items.length})
                      </span>
                      <div className="space-y-1.5">
                        {detail.action_items.map((item, i) => (
                          <div key={i} className="flex items-start gap-2 p-2 bg-white rounded border border-gray-200">
                            <span className={`px-1.5 py-0.5 rounded flex-shrink-0 font-medium ${
                              item.status === "passed" ? "bg-green-100 text-green-700" :
                              item.status === "failed" ? "bg-red-100 text-red-700" :
                              item.status === "tabled" ? "bg-yellow-100 text-yellow-700" :
                              "bg-gray-100 text-gray-600"
                            }`}>
                              {item.status || "pending"}
                            </span>
                            <div className="flex-1 min-w-0">
                              <p className="text-gray-700">{item.description}</p>
                              {(item.assigned_to || item.deadline) && (
                                <p className="text-gray-400 mt-0.5">
                                  {item.assigned_to && <span>Assigned: {item.assigned_to}</span>}
                                  {item.assigned_to && item.deadline && <span> | </span>}
                                  {item.deadline && <span>Deadline: {item.deadline}</span>}
                                </p>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {detail.transcription_preview && (
                    <div>
                      <span className="font-semibold text-gray-700 block mb-1">
                        Transcription Preview ({detail.transcription_length.toLocaleString()} chars)
                      </span>
                      <p className="text-gray-500 leading-relaxed">
                        {detail.transcription_preview.slice(0, 500)}
                        {detail.transcription_length > 500 && "..."}
                      </p>
                    </div>
                  )}

                  {detail.processing_started_at && (
                    <p className="text-gray-400">
                      Started: {new Date(detail.processing_started_at).toLocaleString()}
                      {detail.processing_completed_at && (
                        <span> | Completed: {new Date(detail.processing_completed_at).toLocaleString()}</span>
                      )}
                    </p>
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
