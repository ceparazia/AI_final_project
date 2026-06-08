"""Metrics and public integration entrypoint for C module."""

from __future__ import annotations

from statistics import mean
from typing import Any

try:
    from .debate import get_opinion_counts, run_debate, should_trigger_debate
except ImportError:  # pragma: no cover - supports direct script execution.
    from debate import get_opinion_counts, run_debate, should_trigger_debate


def update_debate_and_metrics(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    """Unified C entrypoint used by A's simulation adapter.

    Reads event/agents/messages/relationships and writes debate/metrics only.
    """
    if should_trigger_debate(state, timestep):
        state = run_debate(state, timestep)
    else:
        debate = state.setdefault(
            "debate",
            {
                "triggered": False,
                "round": 0,
                "claims": [],
                "votes": {},
                "summary": "",
            },
        )
        debate["triggered"] = False

    return update_metrics(state, timestep)


def update_metrics(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    """Append spread rate, confidence and opinion-count metrics."""
    metrics = state.setdefault(
        "metrics",
        {
            "spread_rate": [],
            "average_confidence": [],
            "opinion_count": [],
            "consensus_reached": False,
        },
    )
    agents = state.get("agents", {})
    if not agents:
        metrics["spread_rate"].append({"timestep": timestep, "value": 0.0})
        metrics["average_confidence"].append({"timestep": timestep, "value": 0.0})
        metrics["opinion_count"].append(
            {"timestep": timestep, "believe": 0, "reject": 0, "uncertain": 0}
        )
        metrics["consensus_reached"] = False
        return state

    counts = get_opinion_counts(state)
    agent_count = len(agents)
    spread_rate = counts["believe"] / agent_count
    avg_confidence = mean(
        float(agent.get("confidence", 0.5)) for agent in agents.values()
    )
    consensus_reached = max(counts.values()) / agent_count >= 0.75

    metrics["spread_rate"].append(
        {"timestep": timestep, "value": round(spread_rate, 3)}
    )
    metrics["average_confidence"].append(
        {"timestep": timestep, "value": round(avg_confidence, 3)}
    )
    metrics["opinion_count"].append({"timestep": timestep, **counts})
    metrics["consensus_reached"] = bool(consensus_reached)
    return state

