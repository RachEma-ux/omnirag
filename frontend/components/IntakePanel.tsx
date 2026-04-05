"use client";

import { useState } from "react";
import { api } from "../lib/api";

interface Job {
  id: string;
  state: string;
  files_found: number;
  documents_created: number;
  chunks_created: number;
  errors: string[];
}

export default function IntakePanel() {
  const [source, setSource] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const ingest = async () => {
    if (!source.trim()) return;
    setLoading(true);
    setError("");
    try {
      const job = (await api.ingest(source.trim())) as Job;
      setJobs((prev) => [job, ...prev]);
      setSource("");
    } catch (e: any) {
      setError(e.message || "Ingest failed");
    } finally {
      setLoading(false);
    }
  };

  const refresh = async () => {
    try {
      const list = (await api.listJobs()) as Job[];
      setJobs(list);
    } catch {}
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={source}
          onChange={(e) => setSource(e.target.value)}
          placeholder="File path or URL..."
          className="flex-1 px-3 py-2 bg-[#1e1e1e] border border-[#2a2a2a] rounded text-sm text-white placeholder:text-[#555]"
          onKeyDown={(e) => e.key === "Enter" && ingest()}
        />
        <button
          onClick={ingest}
          disabled={loading}
          className="px-4 py-2 bg-[#6366f1] text-white rounded text-sm font-medium hover:bg-[#818cf8] disabled:opacity-50"
        >
          {loading ? "..." : "Ingest"}
        </button>
        <button
          onClick={refresh}
          className="px-3 py-2 border border-[#2a2a2a] rounded text-sm text-[#888] hover:text-white"
        >
          ↻
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {jobs.length > 0 && (
        <div className="border border-[#2a2a2a] rounded overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#2a2a2a] text-[#888]">
                <th className="text-left px-3 py-2">ID</th>
                <th className="text-left px-3 py-2">State</th>
                <th className="text-right px-3 py-2">Files</th>
                <th className="text-right px-3 py-2">Docs</th>
                <th className="text-right px-3 py-2">Chunks</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id} className="border-b border-[#1c1c1c]">
                  <td className="px-3 py-2 font-mono text-xs">{j.id.slice(0, 8)}</td>
                  <td className="px-3 py-2">
                    <span
                      className={`px-2 py-0.5 rounded text-xs ${
                        j.state === "active"
                          ? "bg-green-900/30 text-green-400"
                          : j.state === "failed"
                          ? "bg-red-900/30 text-red-400"
                          : "bg-yellow-900/30 text-yellow-400"
                      }`}
                    >
                      {j.state}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right">{j.files_found}</td>
                  <td className="px-3 py-2 text-right">{j.documents_created}</td>
                  <td className="px-3 py-2 text-right">{j.chunks_created}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
