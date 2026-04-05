/**
 * OmniRAG Home — main page with 4-tab interface
 * RAG | OmniGraph | Graph | Chat
 */
"use client";

import { useState } from "react";

const TABS = ["RAG", "OmniGraph", "Graph", "Chat"] as const;
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
          <a href="/docs" className="px-2 py-0.5 border border-[#2a2a2a] rounded">API Docs</a>
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
        {activeTab === "RAG" && <RAGTab />}
        {activeTab === "OmniGraph" && <OmniGraphTab />}
        {activeTab === "Graph" && <GraphTab />}
        {activeTab === "Chat" && <ChatTab />}
      </main>

      {/* Footer */}
      <footer className="h-6 shrink-0 flex items-center px-3 border-t border-[#2a2a2a] text-xs text-[#555]">
        <span id="status">OmniRAG v4.0</span>
      </footer>
    </div>
  );
}

function RAGTab() {
  return <div className="max-w-2xl mx-auto"><h2 className="text-lg font-semibold mb-4">RAG</h2><p className="text-[#888]">Intake, pipelines, adapters</p></div>;
}

function OmniGraphTab() {
  return <div className="max-w-2xl mx-auto"><h2 className="text-lg font-semibold mb-4">OmniGraph</h2><p className="text-[#888]">Knowledge graph queries</p></div>;
}

function GraphTab() {
  return <div className="max-w-2xl mx-auto"><h2 className="text-lg font-semibold mb-4">Graph Explorer</h2><p className="text-[#888]">Entity search, community browser</p></div>;
}

function ChatTab() {
  return <div className="max-w-2xl mx-auto"><h2 className="text-lg font-semibold mb-4">Chat</h2><p className="text-[#888]">Ask questions about your documents</p></div>;
}
