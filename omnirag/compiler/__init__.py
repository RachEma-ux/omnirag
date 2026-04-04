"""Selective Execution Planner (Compiler).

Detects deterministic sub-graphs in pipelines and compiles them
into fused Python functions for 1.3-2x speedup.
"""

from omnirag.compiler.planner import CompiledSubgraph, SelectiveExecutionPlanner

__all__ = ["SelectiveExecutionPlanner", "CompiledSubgraph"]
