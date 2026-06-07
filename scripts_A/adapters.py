from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

try:
    from .agent import clamp, count_opinions
except ImportError:  # pragma: no cover - supports direct script execution.
    from agent import clamp, count_opinions


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def update_social_state_adapter(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    """Call B's future module when present, otherwise use A's integration mock."""
    external = _load_function(
        [
            ("social_state", "update_social_state"),
            ("memory", "update_social_state"),
        ]
    )
    if external:
        return external(state, timestep)

    state = update_memory(state, timestep)
    state = update_opinion(state, timestep)
    state = update_relationships(state, timestep)
    state = update_trusted_agents(state)
    return state


def update_debate_and_metrics_adapter(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    """Call C's future module when present, otherwise use A's integration mock."""
    external = _load_function(
        [
            ("evaluation", "update_debate_and_metrics"),
            ("debate", "update_debate_and_metrics"),
        ]
    )
    if external:
        return external(state, timestep)

    if should_trigger_debate(state, timestep):
        state = run_debate(state, timestep)
    state = update_metrics(state, timestep)
    return state


def _load_function(candidates: list[tuple[str, str]]) -> Any | None:
    for module_name, function_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ImportError:
            continue
        function = getattr(module, function_name, None)
        if callable(function):
            return function
    return None


def update_memory(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    current_messages = [m for m in state["messages"] if m["timestep"] == timestep]
    for message in current_messages:
        speaker = message["speaker"]
        receiver = message["receiver"]
        memory_item = {
            "timestep": timestep,
            "speaker": speaker,
            "receiver": receiver,
            "stance": message["stance"],
            "confidence": message["confidence"],
            "content": message["content"],
        }
        state["agents"][speaker]["memory"].append({**memory_item, "direction": "sent"})
        state["agents"][receiver]["memory"].append({**memory_item, "direction": "received"})

    for agent in state["agents"].values():
        agent["memory"] = agent["memory"][-30:]
    return state


def update_opinion(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    current_messages = [m for m in state["messages"] if m["timestep"] == timestep]
    received_by_agent: dict[str, list[dict[str, Any]]] = {agent_id: [] for agent_id in state["agents"]}
    for message in current_messages:
        received_by_agent[message["receiver"]].append(message)

    for agent_id, agent in state["agents"].items():
        opinion_score = _opinion_to_score(agent["opinion"], float(agent["confidence"]))
        personality = agent["personality"]

        for message in received_by_agent.get(agent_id, []):
            speaker_id = message["speaker"]
            speaker = state["agents"][speaker_id]
            relation = state["relationships"].get(agent_id, {}).get(speaker_id, {})
            trust = float(relation.get("trust", 0.55))
            direction = _stance_to_direction(message["stance"])
            confidence = float(message["confidence"])
            influence = confidence * trust * (0.55 + 0.45 * personality["trustfulness"])

            if speaker["role"] == "rational_verifier" and message["stance"] in {"reject", "uncertain"}:
                influence += 0.08 * personality["verification"]
            if not state["event"].get("verified", False):
                influence += 0.03 * speaker["personality"]["verification"]
                if message["stance"] == "believe":
                    influence -= 0.08 * personality["risk_sensitivity"]

            opinion_score += direction * influence * 0.45

        if not state["event"].get("verified", False):
            opinion_score -= 0.06 * personality["risk_sensitivity"]
            opinion_score += 0.04 * personality["activity"] * personality["trustfulness"]

        opinion_score = clamp(opinion_score, -1.0, 1.0)
        if opinion_score >= 0.18:
            agent["opinion"] = "believe"
        elif opinion_score <= -0.18:
            agent["opinion"] = "reject"
        else:
            agent["opinion"] = "uncertain"
        agent["confidence"] = round(clamp(0.45 + abs(opinion_score) * 0.45), 2)

    return state


def update_relationships(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    current_messages = [m for m in state["messages"] if m["timestep"] == timestep]
    for message in current_messages:
        speaker_id = message["speaker"]
        receiver_id = message["receiver"]
        _ensure_relationship(state, speaker_id, receiver_id)
        _ensure_relationship(state, receiver_id, speaker_id)

        forward = state["relationships"][speaker_id][receiver_id]
        reverse = state["relationships"][receiver_id][speaker_id]
        forward["interaction_count"] += 1
        reverse["interaction_count"] += 1

        speaker_opinion = state["agents"][speaker_id]["opinion"]
        receiver_opinion = state["agents"][receiver_id]["opinion"]
        delta = 0.025 if speaker_opinion == receiver_opinion else -0.015

        if state["agents"][speaker_id]["role"] == "rational_verifier" and message["stance"] != "believe":
            delta += 0.02
        if message["stance"] == "believe" and not state["event"].get("verified", False):
            delta -= 0.01 * state["agents"][receiver_id]["personality"]["verification"]

        forward["trust"] = round(clamp(float(forward["trust"]) + delta), 2)
        reverse["trust"] = round(clamp(float(reverse["trust"]) + delta * 0.6), 2)

    return state


def update_trusted_agents(state: dict[str, Any]) -> dict[str, Any]:
    for agent_id, relations in state["relationships"].items():
        trusted = [
            other_id
            for other_id, relation in relations.items()
            if float(relation.get("trust", 0.0)) >= 0.7
        ]
        state["agents"][agent_id]["trusted_agents"] = sorted(trusted)
    return state


def should_trigger_debate(state: dict[str, Any], timestep: int) -> bool:
    counts = count_opinions(state)
    avg_confidence = sum(float(agent["confidence"]) for agent in state["agents"].values()) / len(state["agents"])
    has_conflict = counts["believe"] > 0 and counts["reject"] > 0
    high_uncertainty = counts["uncertain"] > len(state["agents"]) / 2
    low_confidence = avg_confidence < 0.6
    return has_conflict or high_uncertainty or low_confidence


def run_debate(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    debate = state["debate"]
    debate["triggered"] = True
    debate["round"] = int(debate.get("round", 0)) + 1

    for agent_id, agent in state["agents"].items():
        claim = {
            "timestep": timestep,
            "agent": agent_id,
            "stance": agent["opinion"],
            "confidence": agent["confidence"],
            "claim": _claim_text(state, agent_id),
        }
        debate["claims"].append(claim)

    debate["votes"] = {
        agent_id: {
            "vote": agent["opinion"],
            "confidence": agent["confidence"],
        }
        for agent_id, agent in state["agents"].items()
    }
    counts = count_opinions(state)
    debate["summary"] = (
        f"第 {timestep} 轮辩论后，believe={counts['believe']}、"
        f"reject={counts['reject']}、uncertain={counts['uncertain']}。"
        "组织协调者建议等待正式通知，同时保留多角色质疑和投票记录。"
    )
    return state


def update_metrics(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    counts = count_opinions(state)
    agent_count = len(state["agents"])
    avg_confidence = sum(float(agent["confidence"]) for agent in state["agents"].values()) / agent_count
    spread_rate = counts["believe"] / agent_count

    state["metrics"]["spread_rate"].append(
        {"timestep": timestep, "value": round(spread_rate, 3)}
    )
    state["metrics"]["average_confidence"].append(
        {"timestep": timestep, "value": round(avg_confidence, 3)}
    )
    state["metrics"]["opinion_count"].append(
        {"timestep": timestep, **counts}
    )
    state["metrics"]["consensus_reached"] = (
        max(counts.values()) / agent_count >= 0.75 and avg_confidence >= 0.62
    )
    return state


def _ensure_relationship(state: dict[str, Any], source_id: str, target_id: str) -> None:
    state["relationships"].setdefault(source_id, {})
    state["relationships"][source_id].setdefault(
        target_id,
        {"trust": 0.55, "interaction_count": 0},
    )


def _opinion_to_score(opinion: str, confidence: float) -> float:
    if opinion == "believe":
        return confidence
    if opinion == "reject":
        return -confidence
    return 0.0


def _stance_to_direction(stance: str) -> int:
    if stance == "believe":
        return 1
    if stance == "reject":
        return -1
    return 0


def _claim_text(state: dict[str, Any], agent_id: str) -> str:
    agent = state["agents"][agent_id]
    event = state["event"]["content"]
    if agent["role"] == "active_spreader":
        return f"我会分享“{event}”，但需要说明它来自非正式渠道。"
    if agent["role"] == "rational_verifier":
        return "目前没有课程组或教务系统证据，应优先核验来源。"
    if agent["role"] == "coordinator":
        return "群体可以先记录信息，但对外传播前应形成统一、谨慎的说法。"
    return "如果同学直接按开卷准备，风险较高，应提醒大家等待正式通知。"

