# OmniGraph Visualization Upgrade Plan

**Date:** 2026-04-05
**Input:** 3 visualization spec files from `downloads/omnigraph/visualization/`
**Current:** Basic force-directed canvas renderer with drag/zoom/click
**Target:** Professional interactive knowledge graph explorer

---

## 8 Features to Build

### From spec (cherry-picked for value)

| # | Feature | What it adds | Lines est |
|---|---------|-------------|-----------|
| V1 | 3 layout algorithms + switcher | Force-directed, hierarchical (tree), circular. Dropdown to switch. | ~200 |
| V2 | Advanced filtering panel | Filter by entity type (checkboxes), relationship type, weight range (slider), text search | ~250 |
| V3 | Path finding & highlighting | Select 2 nodes → compute shortest path → highlight edges + show path length | ~150 |
| V4 | Community coloring | Color nodes by Leiden community membership instead of entity type | ~100 |
| V5 | Export to image | Download canvas as PNG with legend and timestamp | ~80 |
| V6 | Expand/collapse | Double-click node → fetch neighbors from API → add to graph. Right-click → collapse. | ~150 |

### Added per your request

| # | Feature | What it adds | Lines est |
|---|---------|-------------|-----------|
| V7 | Real-time collaboration | Shared viewport, selections, filters via WebSocket. Multi-cursor. Session link sharing. | ~300 |
| V8 | Annotations & commenting | Right-click node/edge → add comment. Stored in backend. Comment badges on graph. Threaded replies. Side panel. | ~250 |

**Total: ~1,480 lines**

---

## Feature Details

### V1 — Layout Algorithms + Switcher

**Current:** Single force-directed spring layout (custom)

**Upgrade:**
- **Force-directed** (current, improved): repulsion + attraction + center gravity
- **Hierarchical (tree)**: top-down DAG layout, entities sorted by PageRank/level, relationships flow downward. Good for showing community hierarchy or dependency chains.
- **Circular**: entities arranged in a circle, edges as arcs. Grouped by entity type or community. Good for seeing all connections at a glance.

**UI:** Dropdown in toolbar: `Layout: [Force ▾]` switching to `Hierarchy` or `Circular`

**Implementation:**
- `layoutForce()` — existing, clean up
- `layoutHierarchy()` — sort nodes by level/pagerank, assign x=column y=row, edges go top→down
- `layoutCircular()` — arrange nodes in circle by type/community, calculate positions with `2π * i / n`
- Smooth transition between layouts (animate node positions over 500ms)

### V2 — Advanced Filtering Panel

**Current:** Only search by name

**Upgrade:** Collapsible filter panel on the left side of the canvas:
- **Entity type checkboxes**: PERSON ☑, ORG ☑, PRODUCT ☐, PROJECT ☑... (toggle visibility)
- **Relationship type checkboxes**: USES ☑, DEPENDS_ON ☑, RELATED_TO ☐...
- **Weight range slider**: min 0 ─●────── max 5 (hide edges below threshold)
- **Text search**: filter nodes whose name/aliases contain query
- **Community filter**: show only nodes in selected community
- **Reset button**: clear all filters

**Implementation:**
- Filter state object: `{types: Set, relTypes: Set, weightMin: 0, weightMax: 5, search: '', community: null}`
- `drawGraph()` checks each node/edge against filters before rendering
- Filtered nodes/edges are hidden but not removed (toggle back instantly)
- Filter counts shown: "Showing 24 of 47 nodes"

### V3 — Path Finding & Highlighting

**Current:** None

**Upgrade:**
- **Mode:** Click "Path" button in toolbar → enter path-finding mode
- **Select:** Click first node (turns green), click second node (turns red)
- **Compute:** BFS/Dijkstra shortest path through graph edges
- **Display:** Highlighted edges (bright indigo, thick), path nodes get glow
- **Info:** Side panel shows: path length, total weight, node sequence
- **Clear:** "Clear path" button or click elsewhere

**Implementation:**
- `findShortestPath(sourceId, targetId)` — BFS on `graphViz.edges`
- Store `pathNodes` and `pathEdges` sets
- In `drawGraph()`: render path edges on top with different color/thickness
- Works on current in-memory graph (no API call needed)

### V4 — Community Coloring

**Current:** Nodes colored by entity type

**Upgrade:**
- **Toggle:** Button in toolbar: `Color by: [Type ▾]` → switch to `Community`
- **Community mode:** Each node colored by its community_id (generated palette)
- **Community labels:** Show community ID as small badge on nodes
- **Legend updates:** Legend changes to show community colors instead of type colors
- **Data source:** Load communities from `/v1/analytics/communities` or `/graphrag/stats`

**Implementation:**
- Generate color palette for N communities (HSL rotation: `hsl(i * 360/n, 70%, 50%)`)
- Map each node to its community (needs community→entity mapping from backend)
- Add API: `GET /graphrag/entity-communities` → `{entity_id: community_id}`

### V5 — Export to Image

**Current:** None

**Upgrade:**
- **Button:** "📷 Export" in toolbar
- **Output:** PNG image of current canvas view
- **Includes:** Graph + legend + timestamp + node count watermark
- **Method:** `canvas.toDataURL('image/png')` → download link

**Implementation:**
- Draw legend and stats onto a temporary canvas
- Composite: graph canvas + overlay → single image
- Trigger download via `<a>` element with `download` attribute
- ~80 lines

### V6 — Expand/Collapse

**Current:** Static graph (all nodes loaded at once)

**Upgrade:**
- **Expand:** Double-click node → API call to `/graphrag/query/local` with that entity → add returned entities + relationships to graph
- **Loading indicator:** Spinner on the node during API call
- **Collapse:** Right-click node → "Collapse" option → remove all nodes that were added by expanding this node (keep original nodes)
- **Depth tracking:** Track which nodes came from which expansion (tree of expansions)
- **Limit:** Max 50 neighbors per expansion (prevent explosion)

**Implementation:**
- `expandNode(nodeId)` — API call, parse response, add new nodes/edges, run layout
- `collapseNode(nodeId)` — remove nodes added by this expansion
- `expansionTree: Map<nodeId, Set<addedNodeIds>>`
- Context menu (right-click/long-press): "Expand", "Collapse", "Details", "Find path from here"

### V7 — Real-Time Collaboration

**Current:** Single user

**Upgrade:**
- **WebSocket session:** When user opens Graph tab, connect to `ws://localhost:8100/ws/graph`
- **Shared state:** Viewport (offsetX, offsetY, scale), selected node, filters, node positions
- **Broadcasting:** When user pans/zooms/selects/drags → broadcast delta to all connected clients
- **Multi-cursor:** Show other users' cursors as colored dots with username label
- **Session link:** Generate shareable URL with session ID: `?session=abc123`
- **Presence:** Show connected users count in toolbar: "👥 2 connected"
- **Conflict resolution:** Last-write-wins for node positions, merge for filters

**Backend:**
- New WebSocket endpoint: `ws://localhost:8100/ws/graph`
- Message types: `{type: "viewport", data: {offsetX, offsetY, scale}}`, `{type: "select", data: {nodeId}}`, `{type: "cursor", data: {x, y, user}}`, `{type: "filter", data: {...}}`
- Session store: in-memory dict of session_id → connected clients
- Broadcast to all clients in same session

**Implementation:**
- `api/routes/graph_ws.py` — WebSocket endpoint with session management
- JS: connect on tab open, send on interaction, receive and apply
- Multi-cursor rendering: draw colored circles at other users' positions
- Graceful disconnect: remove cursor on close

### V8 — Annotations & Commenting

**Current:** None

**Upgrade:**
- **Add comment:** Right-click node or edge → "Add comment" → text input modal
- **Storage:** `POST /v1/graph/comments` → stored in PostgreSQL table `graph_comments`
- **Display:** Comment badge (💬 count) on nodes with comments
- **Side panel:** Click badge → open comment thread (author, timestamp, markdown text)
- **Threaded replies:** Each comment can have replies (parent_comment_id)
- **Edit/delete:** Author can edit or delete their own comments
- **Mentions:** @username in comment text (future: notification)

**Backend:**
- New table: `graph_comments (id, target_id, target_type, text, author, parent_id, created_at, updated_at)`
- API: `POST/GET/PUT/DELETE /v1/graph/comments`
- On graph load: fetch comment counts per node

**Frontend:**
- Comment modal with textarea
- Badge rendering on canvas (small number next to node)
- Side panel for thread view
- Context menu entry: "💬 Comment (3)"

---

## API Changes Required

| Endpoint | Method | Purpose | Phase |
|----------|--------|---------|-------|
| `GET /graphrag/entity-communities` | GET | Entity → community mapping | V4 |
| `WS /ws/graph` | WebSocket | Real-time collaboration | V7 |
| `POST /v1/graph/comments` | POST | Create comment | V8 |
| `GET /v1/graph/comments?target_id=` | GET | Get comments for node/edge | V8 |
| `PUT /v1/graph/comments/{id}` | PUT | Edit comment | V8 |
| `DELETE /v1/graph/comments/{id}` | DELETE | Delete comment | V8 |
| `GET /v1/graph/comments/counts` | GET | Comment counts per node | V8 |

---

## UI Layout (After Upgrade)

```
┌─ Toolbar ──────────────────────────────────────────────────────┐
│ [Search...] [Search] [Reload] [+Sample]                        │
│ Layout: [Force ▾]  Color: [Type ▾]  [Path] [📷 Export] 👥 2   │
└────────────────────────────────────────────────────────────────┘
┌─ Filter ─┬─ Canvas ────────────────────────────────────────────┐
│ Types:   │                                                      │
│ ☑ PERSON │        ○ EntityA                                     │
│ ☑ ORG    │       / \        ○ cursor:Bob                        │
│ ☐ PRODUCT│      /   \                                           │
│ ☑ PROJECT│  ○──○─────○──○                                       │
│           │      \   /  💬3                                     │
│ Relations:│       \ /                                           │
│ ☑ USES   │        ○ EntityB                                     │
│ ☑ DEPENDS│                                                      │
│           │                              ● PERSON ● ORG ● ...  │
│ Weight:   │                              24/47 nodes · 1.2x     │
│ 0 ──●── 5│                                                      │
│           ├──────────────────────────────────────────────────────┤
│ Community:│ EntityA (PROJECT)                               ✕    │
│ [All ▾]  │ Community: #3 (blue)                                 │
│           │ Connections: 7                                       │
│ [Reset]  │ 💬 Comments (3)                                      │
│           │ → EntityB (USES, w:4)                                │
│ Showing   │ Path: A → C → B (length 2, weight 5.5)             │
│ 24 of 47  │                                                      │
└───────────┴──────────────────────────────────────────────────────┘
```

---

## Build Order

```
V1 (layouts)     → V2 (filters)    → V3 (pathfinding)
                                         ↓
V4 (communities) → V5 (export)     → V6 (expand/collapse)
                                         ↓
                  V7 (collaboration) → V8 (annotations)
```

V1–V6 are independent of backend changes (except V4 needs one new endpoint).
V7 needs a new WebSocket endpoint.
V8 needs a new comments table + CRUD API.

V1–V6 can ship as one release. V7–V8 as a second release.

---

## Estimated Scope

| Phase | Feature | Files Changed | Lines |
|-------|---------|--------------|-------|
| V1 | 3 layouts + switcher | app.js | ~200 |
| V2 | Filter panel | app.js + styles.css | ~250 |
| V3 | Path finding | app.js | ~150 |
| V4 | Community coloring | app.js + 1 API route | ~100 |
| V5 | Export to image | app.js | ~80 |
| V6 | Expand/collapse | app.js | ~150 |
| V7 | Real-time collaboration | app.js + graph_ws.py | ~300 |
| V8 | Annotations | app.js + styles.css + comments.py + schema | ~250 |
| **Total** | | **~6 files** | **~1,480** |

---

Awaiting approval to proceed.
