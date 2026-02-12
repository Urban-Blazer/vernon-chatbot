"use client";

import { useState, useEffect, useCallback } from "react";
import DashboardStats from "./components/DashboardStats";
import TopQuestions from "./components/TopQuestions";
import UnansweredQuestions from "./components/UnansweredQuestions";
import ConversationList from "./components/ConversationList";
import CrawlStatus from "./components/CrawlStatus";
import HourlyChart from "./components/HourlyChart";
import TopicDistribution from "./components/TopicDistribution";
import DocumentUpload from "./components/DocumentUpload";
import AuditLog from "./components/AuditLog";
import CouncilMeetings from "./components/CouncilMeetings";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getAdminKey(): string {
  return sessionStorage.getItem("vernon-admin-key") || "";
}

async function adminFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "X-Admin-Key": getAdminKey(),
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json();
}

export default function AdminPage() {
  const [days, setDays] = useState(30);
  const [summary, setSummary] = useState<any>(null);
  const [topQuestions, setTopQuestions] = useState<any[]>([]);
  const [unanswered, setUnanswered] = useState<any[]>([]);
  const [hourly, setHourly] = useState<any[]>([]);
  const [topics, setTopics] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [s, tq, ua, h, tp] = await Promise.all([
        adminFetch(`/api/admin/analytics/summary?days=${days}`),
        adminFetch(`/api/admin/analytics/top-questions?days=${days}&limit=10`),
        adminFetch(`/api/admin/analytics/unanswered?days=${days}`),
        adminFetch(`/api/admin/analytics/hourly?days=${Math.min(days, 30)}`),
        adminFetch(`/api/admin/analytics/topics?days=${days}`),
      ]);
      setSummary(s);
      setTopQuestions(tq);
      setUnanswered(ua);
      setHourly(h);
      setTopics(tp);
    } catch {
      // Data may be empty on fresh install
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  return (
    <div className="space-y-8">
      {/* Period selector */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-gray-900">Dashboard</h2>
        <div className="flex items-center gap-2">
          <label htmlFor="period" className="text-sm text-gray-500">
            Period:
          </label>
          <select
            id="period"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="border border-gray-300 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
          <button
            onClick={loadData}
            className="ml-2 text-sm text-blue-600 hover:text-blue-800"
          >
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="text-center py-12 text-gray-500">Loading dashboard...</div>
      ) : (
        <>
          {/* Stats cards */}
          <DashboardStats summary={summary} />

          {/* Charts row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <HourlyChart data={hourly} />
            <TopicDistribution data={topics} />
          </div>

          {/* Tables row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <TopQuestions questions={topQuestions} />
            <UnansweredQuestions questions={unanswered} />
          </div>

          {/* Management row */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <CrawlStatus adminFetch={adminFetch} />
            <DocumentUpload adminFetch={adminFetch} />
          </div>

          {/* Council meetings */}
          <CouncilMeetings adminFetch={adminFetch} />

          {/* Conversations */}
          <ConversationList adminFetch={adminFetch} />

          {/* Audit log */}
          <AuditLog adminFetch={adminFetch} />
        </>
      )}
    </div>
  );
}
