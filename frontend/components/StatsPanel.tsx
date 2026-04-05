"use client";

import { useState, useEffect } from "react";
import { api } from "../lib/api";

interface HealthData {
  status: string;
  version: string;
}

interface GraphStats {
  mode: string;
  entities: number;
  relationships: number;
  communities: number;
  reports: number;
}

export default function StatsPanel() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [graphStats, setGraphStats] = useState<GraphStats | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
    api.graphStats().then((s: any) => setGraphStats(s)).catch(() => {});
  }, []);

  const cards = [
    { label: "Status", value: health?.status || "—", color: health?.status === "ok" ? "text-green-400" : "text-red-400" },
    { label: "Version", value: health?.version || "—", color: "text-white" },
    { label: "Graph Mode", value: graphStats?.mode || "—", color: "text-[#6366f1]" },
    { label: "Entities", value: graphStats?.entities ?? "—", color: "text-white" },
    { label: "Relationships", value: graphStats?.relationships ?? "—", color: "text-white" },
    { label: "Communities", value: graphStats?.communities ?? "—", color: "text-white" },
  ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
      {cards.map((c) => (
        <div key={c.label} className="bg-[#151515] border border-[#2a2a2a] rounded-lg p-3">
          <p className="text-xs text-[#888] mb-1">{c.label}</p>
          <p className={`text-lg font-semibold ${c.color}`}>{c.value}</p>
        </div>
      ))}
    </div>
  );
}
