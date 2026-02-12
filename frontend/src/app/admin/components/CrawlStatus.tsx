"use client";

import { useState, useEffect } from "react";

interface CrawlInfo {
  knowledge_base_chunks: number;
  tracked_pages: number;
  cache_size: number;
  last_crawl_time: string | null;
  crawl_in_progress: boolean;
}

interface Props {
  adminFetch: (path: string, options?: RequestInit) => Promise<any>;
}

export default function CrawlStatus({ adminFetch }: Props) {
  const [status, setStatus] = useState<CrawlInfo | null>(null);
  const [crawling, setCrawling] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const data = await adminFetch("/api/admin/crawl-status");
      setStatus(data);
    } catch {
      // empty
    }
  };

  const triggerCrawl = async (full: boolean) => {
    setCrawling(true);
    setMessage("");
    try {
      const data = await adminFetch(`/api/admin/crawl/trigger?full=${full}`, {
        method: "POST",
      });
      setMessage(
        `Crawl complete: ${data.pages_scraped || 0} pages, ${data.chunks_stored || 0} chunks`
      );
      loadStatus();
    } catch {
      setMessage("Crawl failed or timed out");
    } finally {
      setCrawling(false);
    }
  };

  const clearCache = async () => {
    try {
      await adminFetch("/api/admin/cache/clear", { method: "POST" });
      setMessage("Cache cleared");
      loadStatus();
    } catch {
      setMessage("Failed to clear cache");
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">Knowledge Base</h3>
      {!status ? (
        <p className="text-sm text-gray-400">Loading...</p>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <div>
              <p className="text-xs text-gray-500">Chunks</p>
              <p className="text-lg font-semibold text-gray-900">
                {status.knowledge_base_chunks.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Pages</p>
              <p className="text-lg font-semibold text-gray-900">
                {status.tracked_pages.toLocaleString()}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Cached</p>
              <p className="text-lg font-semibold text-gray-900">
                {status.cache_size}
              </p>
            </div>
          </div>

          <div className="text-xs text-gray-400">
            Last crawl:{" "}
            {status.last_crawl_time
              ? new Date(status.last_crawl_time).toLocaleString()
              : "Never"}
          </div>

          {status.crawl_in_progress && (
            <p className="text-sm text-amber-600 font-medium">Crawl in progress...</p>
          )}

          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => triggerCrawl(false)}
              disabled={crawling}
              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {crawling ? "Crawling..." : "Incremental Crawl"}
            </button>
            <button
              onClick={() => triggerCrawl(true)}
              disabled={crawling}
              className="text-xs bg-gray-600 text-white px-3 py-1.5 rounded-lg hover:bg-gray-700 disabled:opacity-50 transition-colors"
            >
              Full Recrawl
            </button>
            <button
              onClick={clearCache}
              className="text-xs border border-gray-300 text-gray-600 px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
            >
              Clear Cache
            </button>
          </div>

          {message && (
            <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded">{message}</p>
          )}
        </div>
      )}
    </div>
  );
}
