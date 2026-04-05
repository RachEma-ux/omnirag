"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { api } from "../lib/api";

interface Node {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  community?: string;
}

interface Edge {
  source: string;
  target: string;
  weight: number;
}

const TYPE_COLORS: Record<string, string> = {
  PERSON: "#6366f1",
  ORG: "#4caf50",
  PRODUCT: "#f59e0b",
  PROJECT: "#06b6d4",
  GPE: "#ec4899",
  EVENT: "#8b5cf6",
  ENTITY: "#888888",
};

export default function GraphVisualization() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [layout, setLayout] = useState<"force" | "circular">("force");
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const dragRef = useRef<{ node: Node | null; offsetX: number; offsetY: number }>({ node: null, offsetX: 0, offsetY: 0 });
  const animRef = useRef<number>(0);

  const loadGraph = useCallback(async () => {
    setLoading(true);
    try {
      const [entityData, statsData] = await Promise.all([
        api.analyticsEntities(),
        api.graphStats(),
      ]);
      setStats(statsData);

      const entities = entityData as any[];
      if (!entities.length) return;

      const w = canvasRef.current?.width || 800;
      const h = canvasRef.current?.height || 600;

      const newNodes: Node[] = entities.map((e: any, i: number) => {
        const angle = (2 * Math.PI * i) / entities.length;
        return {
          id: e.resolved_id || e.id || `e-${i}`,
          name: e.canonical_name || e.name || "?",
          type: e.entity_type || e.type || "ENTITY",
          x: w / 2 + (Math.random() - 0.5) * w * 0.6,
          y: h / 2 + (Math.random() - 0.5) * h * 0.6,
          vx: 0,
          vy: 0,
          community: e.community,
        };
      });

      // Build edges from relationships endpoint
      let newEdges: Edge[] = [];
      try {
        const relData = (await (api as any).analyticsRelationships?.()) || [];
        newEdges = (relData as any[]).map((r: any) => ({
          source: r.source_id || r.source,
          target: r.target_id || r.target,
          weight: r.weight || 1,
        }));
      } catch {
        // Build co-occurrence edges from node proximity
        for (let i = 0; i < newNodes.length; i++) {
          for (let j = i + 1; j < Math.min(i + 3, newNodes.length); j++) {
            newEdges.push({ source: newNodes[i].id, target: newNodes[j].id, weight: 1 });
          }
        }
      }

      setNodes(newNodes);
      setEdges(newEdges);
    } catch {
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadGraph();
  }, [loadGraph]);

  // Force simulation
  useEffect(() => {
    if (!nodes.length || layout !== "force") return;

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    const tick = () => {
      // Repulsion
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const a = nodes[i], b = nodes[j];
          const dx = b.x - a.x, dy = b.y - a.y;
          const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
          const force = 500 / (dist * dist);
          const fx = (dx / dist) * force, fy = (dy / dist) * force;
          a.vx -= fx; a.vy -= fy;
          b.vx += fx; b.vy += fy;
        }
      }

      // Attraction (edges)
      for (const e of edges) {
        const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const force = (dist - 80) * 0.01;
        const fx = (dx / Math.max(dist, 1)) * force;
        const fy = (dy / Math.max(dist, 1)) * force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }

      // Center gravity
      const w = canvasRef.current?.width || 800;
      const h = canvasRef.current?.height || 600;
      for (const n of nodes) {
        n.vx += (w / 2 - n.x) * 0.001;
        n.vy += (h / 2 - n.y) * 0.001;
        n.vx *= 0.9; n.vy *= 0.9;
        if (!dragRef.current.node || dragRef.current.node.id !== n.id) {
          n.x += n.vx; n.y += n.vy;
        }
      }

      draw();
      animRef.current = requestAnimationFrame(tick);
    };

    animRef.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animRef.current);
  }, [nodes, edges, layout]);

  // Circular layout
  useEffect(() => {
    if (layout !== "circular" || !nodes.length) return;
    const w = canvasRef.current?.width || 800;
    const h = canvasRef.current?.height || 600;
    const r = Math.min(w, h) * 0.35;
    nodes.forEach((n, i) => {
      const angle = (2 * Math.PI * i) / nodes.length;
      n.x = w / 2 + r * Math.cos(angle);
      n.y = h / 2 + r * Math.sin(angle);
      n.vx = 0; n.vy = 0;
    });
    draw();
  }, [layout, nodes.length]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const nodeMap = new Map(nodes.map((n) => [n.id, n]));

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Edges
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.lineWidth = 1;
    for (const e of edges) {
      const a = nodeMap.get(e.source), b = nodeMap.get(e.target);
      if (!a || !b) continue;
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
    }

    // Nodes
    for (const n of nodes) {
      const color = TYPE_COLORS[n.type] || TYPE_COLORS.ENTITY;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 6, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();

      // Label
      ctx.fillStyle = "#e8e8e8";
      ctx.font = "10px sans-serif";
      ctx.fillText(n.name, n.x + 9, n.y + 3);
    }
  }, [nodes, edges]);

  // Drag handling
  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    for (const n of nodes) {
      if (Math.abs(n.x - mx) < 10 && Math.abs(n.y - my) < 10) {
        dragRef.current = { node: n, offsetX: mx - n.x, offsetY: my - n.y };
        return;
      }
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!dragRef.current.node) return;
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    dragRef.current.node.x = e.clientX - rect.left - dragRef.current.offsetX;
    dragRef.current.node.y = e.clientY - rect.top - dragRef.current.offsetY;
    if (layout === "circular") draw();
  };

  const handleMouseUp = () => {
    dragRef.current.node = null;
  };

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center gap-3 text-sm">
        <button onClick={loadGraph} disabled={loading} className="px-3 py-1.5 bg-[#6366f1] text-white rounded text-xs hover:bg-[#818cf8] disabled:opacity-50">
          {loading ? "Loading..." : "Load Graph"}
        </button>
        <select value={layout} onChange={(e) => setLayout(e.target.value as any)} className="px-2 py-1.5 bg-[#1e1e1e] border border-[#2a2a2a] rounded text-xs text-white">
          <option value="force">Force</option>
          <option value="circular">Circular</option>
        </select>
        {stats && (
          <span className="text-xs text-[#888]">
            {stats.entities} entities · {stats.relationships} rels · {stats.communities} communities
          </span>
        )}
        {/* Legend */}
        <div className="flex gap-2 ml-auto">
          {Object.entries(TYPE_COLORS).slice(0, 5).map(([type, color]) => (
            <span key={type} className="flex items-center gap-1 text-xs text-[#888]">
              <span className="inline-block w-2 h-2 rounded-full" style={{ background: color }} />
              {type}
            </span>
          ))}
        </div>
      </div>

      {/* Canvas */}
      <canvas
        ref={canvasRef}
        width={900}
        height={550}
        className="w-full border border-[#2a2a2a] rounded bg-[#0a0a0a] cursor-grab active:cursor-grabbing"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
      />
    </div>
  );
}
