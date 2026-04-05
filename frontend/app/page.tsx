"use client";

import { useState } from "react";
import IntakePanel from "../components/IntakePanel";
import GraphExplorer from "../components/GraphExplorer";
import ChatInterface from "../components/ChatInterface";
import StatsPanel from "../components/StatsPanel";

const TABS = ["RAG", "OmniGraph", "Visualization", "Chat"] as const;
type Tab = (typeof TABS)[number];

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>("RAG");

  return (
    <div className="flex flex-col h-dvh overflow-hidden">
      {/* Titlebar */}
      <header className="h-10 shrink-0 flex items-center justify-between px-3 border-b border-[#2a2a2a]">
        <div className="font-semibold text-sm">
          <span className="text-[#6366f1]">Omni</span>RAG
        </div>
        <div className="flex gap-2 text-xs text-[#888]">
          <a href="/docs" className="px-2 py-0.5 border border-[#2a2a2a] rounded hover:text-white">
            API Docs
          </a>
          <a href="/redoc" className="px-2 py-0.5 border border-[#2a2a2a] rounded hover:text-white">
            ReDoc
          </a>
        </div>
      </header>

      {/* Tab Bar */}
      <div className="flex shrink-0 border-b border-[#2a2a2a]">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`flex-1 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab
                ? "text-white border-b-2 border-white"
                : "text-[#666] hover:text-[#aaa]"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <main className="flex-1 overflow-y-auto p-6">
        {activeTab === "RAG" && (
          <div className="max-w-3xl mx-auto space-y-6">
            <h2 className="text-lg font-semibold">Intake & Retrieval</h2>
            <StatsPanel />
            <IntakePanel />
          </div>
        )}
        {activeTab === "OmniGraph" && (
          <div className="max-w-3xl mx-auto space-y-6">
            <h2 className="text-lg font-semibold">Knowledge Graph</h2>
            <GraphExplorer />
          </div>
        )}
        {activeTab === "Visualization" && (
          <div className="max-w-3xl mx-auto">
            <h2 className="text-lg font-semibold mb-4">Graph Visualization</h2>
            <p className="text-[#888] text-sm">
              Interactive knowledge graph — available at{" "}
              <a href="http://localhost:8100" className="text-[#6366f1] underline">
                localhost:8100
              </a>{" "}
              (canvas-based visualization with force layout, path finding, filtering)
            </p>
          </div>
        )}
        {activeTab === "Chat" && <ChatInterface />}
      </main>

      {/* Footer */}
      <footer className="h-6 shrink-0 flex items-center px-3 border-t border-[#2a2a2a] text-xs text-[#555]">
        <span>OmniRAG v4.0</span>
      </footer>
    </div>
  );
}
