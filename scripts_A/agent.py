from __future__ import annotations

import copy
import json
import random
from pathlib import Path
from typing import Any


OPINIONS = {"believe", "reject", "uncertain"}

DEFAULT_EVENT = {
    "event_id": "exam_policy_change",
    "content": "某课程考试形式可能从闭卷调整为开卷，具体安排尚未确认。",
    "source": "anonymous_message",
    "verified": False,
}

AGENT_CONFIGS: dict[str, dict[str, Any]] = {
    "agent_1": {
        "name": "信息传播者",
        "role": "active_spreader",
        "personality": {
            "activity": 0.9,
            "trustfulness": 0.7,
            "verification": 0.3,
            "risk_sensitivity": 0.5,
        },
        "opinion": "believe",
        "confidence": 0.62,
        "memory": [],
        "trusted_agents": [],
    },
    "agent_2": {
        "name": "理性验证者",
        "role": "rational_verifier",
        "personality": {
            "activity": 0.65,
            "trustfulness": 0.35,
            "verification": 0.92,
            "risk_sensitivity": 0.55,
        },
        "opinion": "uncertain",
        "confidence": 0.56,
        "memory": [],
        "trusted_agents": [],
    },
    "agent_3": {
        "name": "组织协调者",
        "role": "coordinator",
        "personality": {
            "activity": 0.75,
            "trustfulness": 0.52,
            "verification": 0.75,
            "risk_sensitivity": 0.68,
        },
        "opinion": "uncertain",
        "confidence": 0.52,
        "memory": [],
        "trusted_agents": [],
    },
    "agent_4": {
        "name": "风险敏感者",
        "role": "risk_sensitive",
        "personality": {
            "activity": 0.7,
            "trustfulness": 0.42,
            "verification": 0.7,
            "risk_sensitivity": 0.92,
        },
        "opinion": "reject",
        "confidence": 0.61,
        "memory": [],
        "trusted_agents": [],
    },
}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def init_state(event_content: str | None = None) -> dict[str, Any]:
    """Create the shared state dict required by section 5.1 of the plan."""
    event = copy.deepcopy(DEFAULT_EVENT)
    if event_content:
        event["content"] = event_content

    agents = copy.deepcopy(AGENT_CONFIGS)
    relationships = _init_relationships(agents)

    return {
        "event": event,
        "agents": agents,
        "messages": [],
        "relationships": relationships,
        "debate": {
            "triggered": False,
            "round": 0,
            "claims": [],
            "votes": {},
            "summary": "",
        },
        "metrics": {
            "spread_rate": [],
            "average_confidence": [],
            "opinion_count": [],
            "consensus_reached": False,
        },
        "timeline": [],
    }


def _init_relationships(agents: dict[str, dict[str, Any]]) -> dict[str, dict[str, dict[str, Any]]]:
    relationships: dict[str, dict[str, dict[str, Any]]] = {}
    for source_id, source in agents.items():
        relationships[source_id] = {}
        for target_id, target in agents.items():
            if source_id == target_id:
                continue
            trust = 0.56
            if source["role"] == "coordinator" or target["role"] == "coordinator":
                trust += 0.04
            if target["role"] == "rational_verifier":
                trust += 0.05
            relationships[source_id][target_id] = {
                "trust": round(clamp(trust), 2),
                "interaction_count": 0,
            }
    return relationships


def select_interactions(state: dict[str, Any], timestep: int) -> list[tuple[str, str]]:
    """Select one receiver for each agent with a deterministic personality-aware policy."""
    rng = random.Random(20260607 + timestep)
    agents = state["agents"]
    agent_ids = sorted(agents)
    pairs: list[tuple[str, str]] = []

    for speaker_id in agent_ids:
        candidates = [agent_id for agent_id in agent_ids if agent_id != speaker_id]
        rng.shuffle(candidates)
        receiver_id = max(
            candidates,
            key=lambda candidate_id: _interaction_score(state, speaker_id, candidate_id, timestep, rng),
        )
        pairs.append((speaker_id, receiver_id))

    return pairs


def _interaction_score(
    state: dict[str, Any],
    speaker_id: str,
    receiver_id: str,
    timestep: int,
    rng: random.Random,
) -> float:
    speaker = state["agents"][speaker_id]
    receiver = state["agents"][receiver_id]
    personality = speaker["personality"]
    relation = state["relationships"].get(speaker_id, {}).get(receiver_id, {})
    trust = float(relation.get("trust", 0.5))
    interaction_count = int(relation.get("interaction_count", 0))

    novelty_bonus = 0.15 / (1 + interaction_count)
    role_bonus = 0.0
    if speaker["role"] == "active_spreader" and receiver["role"] in {"rational_verifier", "coordinator"}:
        role_bonus += 0.12
    if speaker["role"] == "rational_verifier" and receiver["opinion"] == "believe":
        role_bonus += 0.16
    if speaker["role"] == "risk_sensitive" and receiver["opinion"] != "reject":
        role_bonus += 0.14
    if speaker["role"] == "coordinator":
        role_bonus += 0.08

    return (
        personality["activity"] * 0.35
        + trust * 0.35
        + novelty_bonus
        + role_bonus
        + ((timestep + 1) % 3) * 0.01
        + rng.random() * 0.04
    )


def validate_message(
    state: dict[str, Any],
    message: dict[str, Any],
    speaker_id: str,
    receiver_id: str,
    timestep: int,
) -> dict[str, Any]:
    """Coerce a raw message into the exact shared message shape."""
    stance = str(message.get("stance", "uncertain")).strip().lower()
    if stance not in OPINIONS:
        stance = "uncertain"

    try:
        confidence = float(message.get("confidence", 0.5))
    except (TypeError, ValueError):
        confidence = 0.5

    content = str(message.get("content", "")).strip()
    if not content:
        speaker_name = state["agents"][speaker_id]["name"]
        event = state["event"]["content"]
        content = f"{speaker_name}认为这条信息仍需谨慎处理：{event}"

    return {
        "timestep": int(timestep),
        "speaker": speaker_id,
        "receiver": receiver_id,
        "content": content,
        "stance": stance,
        "confidence": round(clamp(confidence), 2),
    }


def create_timeline_snapshot(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    agents = state["agents"]
    opinion_count = count_opinions(state)
    avg_confidence = round(
        sum(float(agent["confidence"]) for agent in agents.values()) / max(len(agents), 1),
        3,
    )
    spread_rate = round(opinion_count["believe"] / max(len(agents), 1), 3)

    return {
        "timestep": timestep,
        "event_id": state["event"]["event_id"],
        "opinion_count": opinion_count,
        "spread_rate": spread_rate,
        "average_confidence": avg_confidence,
        "debate_triggered": bool(state["debate"]["triggered"]),
        "agent_status": {
            agent_id: {
                "opinion": agent["opinion"],
                "confidence": round(float(agent["confidence"]), 2),
                "trusted_agents": list(agent.get("trusted_agents", [])),
            }
            for agent_id, agent in agents.items()
        },
        "message_count": len([m for m in state["messages"] if m["timestep"] == timestep]),
    }


def count_opinions(state: dict[str, Any]) -> dict[str, int]:
    counts = {"believe": 0, "reject": 0, "uncertain": 0}
    for agent in state["agents"].values():
        opinion = agent.get("opinion", "uncertain")
        if opinion not in counts:
            opinion = "uncertain"
        counts[opinion] += 1
    return counts


def save_state(state: dict[str, Any], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

