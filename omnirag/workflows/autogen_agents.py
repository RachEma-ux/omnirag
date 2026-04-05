"""AutoGen-style multi-agent collaboration.

Roles: Researcher (searches graph), Analyst (synthesizes), Reviewer (validates)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AgentMessage:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentConfig:
    name: str
    role: str  # researcher | analyst | reviewer
    model: str = "llama3"
    system_prompt: str = ""


RESEARCHER_PROMPT = """You are a Research Agent. Your job is to search the knowledge graph and find relevant entities, relationships, and evidence for the given query. Return structured findings."""

ANALYST_PROMPT = """You are an Analyst Agent. Given the researcher's findings, synthesize a coherent narrative that answers the query. Include citations to specific entities and chunks."""

REVIEWER_PROMPT = """You are a Reviewer Agent. Check the analyst's answer for accuracy, completeness, and proper citations. Flag any unsupported claims. Approve or request revision."""


class MultiAgentSession:
    """Orchestrates multi-agent collaboration."""

    def __init__(self) -> None:
        self.agents: dict[str, AgentConfig] = {
            "researcher": AgentConfig(name="Researcher", role="researcher", system_prompt=RESEARCHER_PROMPT),
            "analyst": AgentConfig(name="Analyst", role="analyst", system_prompt=ANALYST_PROMPT),
            "reviewer": AgentConfig(name="Reviewer", role="reviewer", system_prompt=REVIEWER_PROMPT),
        }
        self.history: list[AgentMessage] = []

    async def run(self, query: str, max_rounds: int = 3) -> dict:
        """Run a multi-agent collaboration on a query."""
        from omnirag.output.generation.engine import get_generation_engine
        engine = get_generation_engine()

        result = {"query": query, "rounds": [], "final_answer": "", "approved": False}

        for round_num in range(max_rounds):
            round_data = {"round": round_num + 1, "messages": []}

            # Researcher
            research_prompt = f"{self.agents['researcher'].system_prompt}\n\nQuery: {query}\n\nPrevious context: {self._last_messages(2)}\n\nFindings:"
            try:
                research_result = await engine.generate(research_prompt, [])
                research_msg = AgentMessage(role="researcher", content=research_result.answer)
                self.history.append(research_msg)
                round_data["messages"].append({"role": "researcher", "content": research_result.answer[:500]})
            except Exception as e:
                round_data["messages"].append({"role": "researcher", "error": str(e)})
                break

            # Analyst
            analyst_prompt = f"{self.agents['analyst'].system_prompt}\n\nQuery: {query}\n\nResearcher findings: {research_result.answer}\n\nAnalysis:"
            try:
                analyst_result = await engine.generate(analyst_prompt, [])
                analyst_msg = AgentMessage(role="analyst", content=analyst_result.answer)
                self.history.append(analyst_msg)
                round_data["messages"].append({"role": "analyst", "content": analyst_result.answer[:500]})
            except Exception as e:
                round_data["messages"].append({"role": "analyst", "error": str(e)})
                break

            # Reviewer
            reviewer_prompt = f"{self.agents['reviewer'].system_prompt}\n\nQuery: {query}\n\nAnalyst answer: {analyst_result.answer}\n\nReview (APPROVE or REVISE):"
            try:
                reviewer_result = await engine.generate(reviewer_prompt, [])
                reviewer_msg = AgentMessage(role="reviewer", content=reviewer_result.answer)
                self.history.append(reviewer_msg)
                round_data["messages"].append({"role": "reviewer", "content": reviewer_result.answer[:500]})

                if "APPROVE" in reviewer_result.answer.upper():
                    result["final_answer"] = analyst_result.answer
                    result["approved"] = True
                    result["rounds"].append(round_data)
                    break
            except Exception as e:
                round_data["messages"].append({"role": "reviewer", "error": str(e)})
                break

            result["rounds"].append(round_data)

        if not result["final_answer"] and self.history:
            # Use last analyst response as fallback
            analyst_msgs = [m for m in self.history if m.role == "analyst"]
            if analyst_msgs:
                result["final_answer"] = analyst_msgs[-1].content

        return result

    def _last_messages(self, n: int) -> str:
        return "\n".join(f"[{m.role}]: {m.content[:200]}" for m in self.history[-n:])
