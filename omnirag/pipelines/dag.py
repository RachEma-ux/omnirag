"""Pipeline DAG — directed acyclic graph for stage execution ordering."""

from __future__ import annotations

from collections import defaultdict, deque

from omnirag.pipelines.schema import PipelineConfig, StageConfig


class PipelineDAG:
    """Directed acyclic graph representation of a pipeline.

    Nodes are stages, edges are data dependencies.
    Provides topological sort for execution ordering.
    """

    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self._nodes: dict[str, StageConfig] = {s.id: s for s in config.stages}
        self._edges: dict[str, list[str]] = defaultdict(list)  # parent -> children
        self._reverse: dict[str, list[str]] = defaultdict(list)  # child -> parents
        self._build_edges()

    def _build_edges(self) -> None:
        """Build adjacency lists from stage input/depends_on references."""
        for stage in self.config.stages:
            if stage.input and stage.input != "query" and stage.input in self._nodes:
                self._edges[stage.input].append(stage.id)
                self._reverse[stage.id].append(stage.input)
            for dep in stage.depends_on:
                if dep in self._nodes:
                    self._edges[dep].append(stage.id)
                    self._reverse[stage.id].append(dep)

    def topological_sort(self) -> list[str]:
        """Return stage IDs in topological execution order (Kahn's algorithm)."""
        in_degree: dict[str, int] = {node: 0 for node in self._nodes}
        for children in self._edges.values():
            for child in children:
                in_degree[child] += 1

        queue: deque[str] = deque(
            node for node, deg in in_degree.items() if deg == 0
        )
        order: list[str] = []

        while queue:
            node = queue.popleft()
            order.append(node)
            for child in self._edges.get(node, []):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    queue.append(child)

        if len(order) != len(self._nodes):
            missing = set(self._nodes) - set(order)
            raise RuntimeError(f"Cycle detected — unreachable stages: {missing}")

        return order

    def get_stage(self, stage_id: str) -> StageConfig:
        """Get stage config by ID."""
        return self._nodes[stage_id]

    def get_parents(self, stage_id: str) -> list[str]:
        """Get parent stage IDs (stages this one depends on)."""
        return self._reverse.get(stage_id, [])

    def get_children(self, stage_id: str) -> list[str]:
        """Get child stage IDs (stages that depend on this one)."""
        return self._edges.get(stage_id, [])

    def root_stages(self) -> list[str]:
        """Get stages with no dependencies (entry points)."""
        return [sid for sid in self._nodes if not self._reverse.get(sid)]

    def leaf_stages(self) -> list[str]:
        """Get stages with no dependents (exit points)."""
        return [sid for sid in self._nodes if not self._edges.get(sid)]

    @property
    def stage_count(self) -> int:
        return len(self._nodes)
