"use client";

import { useState, useEffect } from "react";
import { api } from "../lib/api";

interface Stats {
  mode: string;
  entities: number;
  relationships: number;
  communities: number;
  reports: number;
}

export default function GraphExplorer() {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState("local");
  const [result, setResult] = useState<any>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.graphStats().then((s: any) => setStats(s)).catch(() => {});
  }, []);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const r = await api.graphQuery(mode, query.trim());
      setResult(r);
    } catch (e: any) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  const autoRoute = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      const r = await api.graphRoute(query.trim());
      setResult(r);
    } catch (e: any) {
      setResult({ error: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Stats bar */}
      {stats && (
        <div className="flex gap-4 text-xs text-[#888]">
          <span>Mode: <span className="text-white">{stats.mode}</span></span>
          <span>Entities: <span className="text-white">{stats.entities}</span></span>
          <span>Relationships: <span className="text-white">{stats.relationships}</span></span>
          <span>Communities: <span className="text-white">{stats.communities}</span></span>
        </div>
      )}

      {/* Query bar */}
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Query the knowledge graph..."
          className="flex-1 px-3 py-2 bg-[#1e1e1e] border border-[#2a2a2a] rounded text-sm text-white placeholder:text-[#555]"
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <select
          value={mode}
          onChange={(e) => setMode(e.target.value)}
          className="px-3 py-2 bg-[#1e1e1e] border border-[#2a2a2a] rounded text-sm text-white"
        >
          <option value="basic">Basic</option>
          <option value="local">Local</option>
          <option value="global">Global</option>
          <option value="drift">DRIFT</option>
        </select>
        <button
          onClick={search}
          disabled={loading}
          className="px-4 py-2 bg-[#6366f1] text-white rounded text-sm font-medium hover:bg-[#818cf8] disabled:opacity-50"
        >
          Search
        </button>
        <button
          onClick={autoRoute}
          disabled={loading}
          className="px-3 py-2 border border-[#6366f1] text-[#6366f1] rounded text-sm hover:bg-[#6366f1]/10"
        >
          Auto Route
        </button>
      </div>

      {/* Results */}
      {result && (
        <div className="border border-[#2a2a2a] rounded p-4">
          {result.error ? (
            <p className="text-red-400">{result.error}</p>
          ) : (
            <div className="space-y-3">
              {result.answer && (
                <div>
                  <h3 className="text-sm font-semibold text-[#888] mb-1">Answer</h3>
                  <p className="text-sm whitespace-pre-wrap">{result.answer}</p>
                </div>
              )}
              {result.mode && (
                <p className="text-xs text-[#555]">Mode: {result.mode}</p>
              )}
              {result.entities && result.entities.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[#888] mb-1">
                    Entities ({result.entities.length})
                  </h3>
                  <div className="flex flex-wrap gap-1">
                    {result.entities.slice(0, 20).map((e: any, i: number) => (
                      <span
                        key={i}
                        className="px-2 py-0.5 bg-[#1e1e1e] border border-[#2a2a2a] rounded text-xs"
                      >
                        {e.canonical_name || e.name || e.resolved_id}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {result.evidence && result.evidence.length > 0 && (
                <div>
                  <h3 className="text-sm font-semibold text-[#888] mb-1">Evidence</h3>
                  {result.evidence.map((ev: any, i: number) => (
                    <p key={i} className="text-xs text-[#888] mb-1">
                      {typeof ev === "string" ? ev : JSON.stringify(ev)}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
