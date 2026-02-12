"use client";

import { useState, useEffect } from "react";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const [apiKey, setApiKey] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [error, setError] = useState("");
  const [checking, setChecking] = useState(true);

  const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  useEffect(() => {
    const stored = sessionStorage.getItem("vernon-admin-key");
    if (stored) {
      verifyKey(stored);
    } else {
      setChecking(false);
    }
  }, []);

  const verifyKey = async (key: string) => {
    setChecking(true);
    setError("");
    try {
      const res = await fetch(`${API_URL}/api/admin/analytics/summary?days=1`, {
        headers: { "X-Admin-Key": key },
      });
      if (res.ok) {
        sessionStorage.setItem("vernon-admin-key", key);
        setAuthenticated(true);
      } else {
        sessionStorage.removeItem("vernon-admin-key");
        setError("Invalid API key");
      }
    } catch {
      setError("Cannot connect to server");
    } finally {
      setChecking(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (apiKey.trim()) {
      verifyKey(apiKey.trim());
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem("vernon-admin-key");
    setAuthenticated(false);
    setApiKey("");
  };

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500">Verifying access...</p>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-xl shadow-lg p-8 w-full max-w-md">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Admin Dashboard</h1>
          <p className="text-sm text-gray-500 mb-6">Enter your admin API key to continue.</p>
          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Admin API Key"
              className="w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              autoFocus
            />
            {error && <p className="text-sm text-red-600">{error}</p>}
            <button
              type="submit"
              className="w-full bg-blue-600 text-white py-2.5 rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
            >
              Sign In
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-bold text-gray-900">Vernon Chatbot Admin</h1>
            <a href="/" className="text-sm text-blue-600 hover:text-blue-800">
              &larr; Back to Chat
            </a>
          </div>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-500 hover:text-gray-700 transition-colors"
          >
            Sign Out
          </button>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
