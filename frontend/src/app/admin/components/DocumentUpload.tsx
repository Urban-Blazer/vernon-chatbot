"use client";

import { useState, useEffect, useRef } from "react";

interface Document {
  url: string;
  filename: string;
  title: string;
  last_crawled: string;
}

interface Props {
  adminFetch: (path: string, options?: RequestInit) => Promise<any>;
}

export default function DocumentUpload({ adminFetch }: Props) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    try {
      const data = await adminFetch("/api/admin/documents");
      setDocuments(data);
    } catch {
      // empty
    }
  };

  const uploadFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setMessage("Only PDF files are supported");
      return;
    }

    setUploading(true);
    setMessage("");

    const formData = new FormData();
    formData.append("file", file);

    try {
      const key = sessionStorage.getItem("vernon-admin-key") || "";
      const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
      const res = await fetch(`${API_URL}/api/ingest/documents`, {
        method: "POST",
        headers: { "X-Admin-Key": key },
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }

      const data = await res.json();
      setMessage(`Uploaded "${data.title}" - ${data.chunks_stored} chunks indexed`);
      loadDocuments();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  };

  const deleteDocument = async (filename: string) => {
    try {
      await adminFetch(`/api/admin/documents/${encodeURIComponent(filename)}`, {
        method: "DELETE",
      });
      setMessage(`Deleted "${filename}"`);
      loadDocuments();
    } catch {
      setMessage("Delete failed");
    }
  };

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5">
      <h3 className="text-sm font-semibold text-gray-900 mb-4">PDF Documents</h3>

      {/* Upload area */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          dragOver ? "border-blue-400 bg-blue-50" : "border-gray-200 hover:border-gray-300"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />
        <p className="text-sm text-gray-500">
          {uploading ? "Uploading..." : "Drop a PDF here or click to upload"}
        </p>
        <p className="text-xs text-gray-400 mt-1">Bylaws, permits, forms, reports</p>
      </div>

      {message && (
        <p className="text-xs text-gray-600 bg-gray-50 p-2 rounded mt-3">{message}</p>
      )}

      {/* Document list */}
      {documents.length > 0 && (
        <div className="mt-4 space-y-2">
          <p className="text-xs text-gray-500 font-medium">Uploaded Documents ({documents.length})</p>
          {documents.map((doc) => (
            <div key={doc.url} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-gray-700 truncate">{doc.title}</p>
                <p className="text-xs text-gray-400">{doc.filename}</p>
              </div>
              <button
                onClick={() => deleteDocument(doc.filename)}
                className="text-xs text-red-500 hover:text-red-700 ml-2 flex-shrink-0"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
