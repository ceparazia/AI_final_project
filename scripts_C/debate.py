"""Debate engine for C module: debate, confidence and voting.

The module follows the shared ``state`` format in the project plan. It reads
``event``, ``agents``, ``messages`` and ``relationships``; it writes only the
``debate`` field through ``run_debate``.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


OPINIONS = ("believe", "reject", "uncertain")


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    """Keep confidence and score values inside the agreed 0.0-1.0 range."""
    return max(lower, min(upper, value))


def get_opinion_counts(state: dict[str, Any]) -> dict[str, int]:
    """Count current opinions using the shared opinion labels."""
    counts = Counter()
    for agent in state.get("agents", {}).values():
        opinion = agent.get("opinion", "uncertain")
        if opinion not in OPINIONS:
            opinion = "uncertain"
        counts[opinion] += 1
    return {opinion: counts.get(opinion, 0) for opinion in OPINIONS}


def should_trigger_debate(state: dict[str, Any], timestep: int) -> bool:
    """Return whether controversy is high enough to enter debate mode."""
    agents = state.get("agents", {})
    if not agents:
        return False

    counts = get_opinion_counts(state)
    avg_confidence = sum(
        float(agent.get("confidence", 0.5)) for agent in agents.values()
    ) / len(agents)

    has_conflict = counts["believe"] > 0 and counts["reject"] > 0
    low_confidence = avg_confidence < 0.6
    high_uncertainty = counts["uncertain"] > len(agents) / 2
    return has_conflict or low_confidence or high_uncertainty


def run_debate(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    """Generate claims, votes and a coordinator-style debate summary."""
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

    claims = [
        _build_claim(state, agent_id, timestep)
        for agent_id in sorted(state.get("agents", {}))
    ]
    votes = {}
    for agent_id in sorted(state.get("agents", {})):
        vote, confidence = _score_vote(state, agent_id)
        agent = state["agents"][agent_id]
        votes[agent_id] = {
            "agent_name": agent.get("name", agent_id),
            "vote": vote,
            "confidence": confidence,
            "continue_spreading": vote == "believe" and confidence >= 0.65,
        }

    debate["triggered"] = True
    debate["round"] = int(debate.get("round", 0)) + 1
    debate["claims"] = claims
    debate["votes"] = votes
    debate["summary"] = _summarize_debate(state, claims, votes)
    return state


def _build_claim(state: dict[str, Any], agent_id: str, timestep: int) -> dict[str, Any]:
    agent = state["agents"][agent_id]
    opinion = _valid_opinion(agent.get("opinion", "uncertain"))
    confidence = clamp(float(agent.get("confidence", 0.5)))
    personality = agent.get("personality", {})
    verification = float(personality.get("verification", 0.5))
    risk = float(personality.get("risk_sensitivity", 0.5))
    trustfulness = float(personality.get("trustfulness", 0.5))
    recent = _recent_messages_for_agent(state, agent_id, timestep)

    if opinion == "believe":
        reason = "近期收到的信息与自身判断较一致"
        if trustfulness >= 0.65:
            reason += "，且角色本身较愿意相信同伴消息"
    elif opinion == "reject":
        reason = "目前证据不足或消息来源仍有风险"
        if verification >= 0.65:
            reason += "，因此倾向先验证再传播"
    else:
        reason = "现有证据不足，暂时保持观望"
        if risk >= 0.65:
            reason += "，并提醒群体注意不确定风险"

    if recent:
        last = recent[-1]
        reason += (
            f"；最近参考了 {last.get('speaker', 'unknown')} "
            f"对 {last.get('receiver', 'unknown')} 的交流"
        )

    return {
        "timestep": timestep,
        "agent_id": agent_id,
        "agent_name": agent.get("name", agent_id),
        "role": agent.get("role", ""),
        "stance": opinion,
        "confidence": round(confidence, 3),
        "claim": f"{agent.get('name', agent_id)}认为应当 {opinion}：{reason}。",
    }


def _score_vote(state: dict[str, Any], agent_id: str) -> tuple[str, float]:
    """Score final vote from stance, confidence, personality and trust."""
    agent = state["agents"][agent_id]
    opinion = _valid_opinion(agent.get("opinion", "uncertain"))
    confidence = clamp(float(agent.get("confidence", 0.5)))
    personality = agent.get("personality", {})
    verification = float(personality.get("verification", 0.5))
    risk = float(personality.get("risk_sensitivity", 0.5))
    trustfulness = float(personality.get("trustfulness", 0.5))

    scores = {"believe": 0.0, "reject": 0.0, "uncertain": 0.0}
    if opinion == "believe":
        scores["believe"] += confidence + 0.25 * trustfulness
    elif opinion == "reject":
        scores["reject"] += confidence + 0.25 * verification
    else:
        scores["uncertain"] += 0.5 + 0.2 * risk

    for neighbor_id, relation in state.get("relationships", {}).get(agent_id, {}).items():
        if neighbor_id not in state.get("agents", {}):
            continue
        trust = float(relation.get("trust", 0.0))
        if trust < 0.65:
            continue
        neighbor_opinion = _valid_opinion(
            state["agents"][neighbor_id].get("opinion", "uncertain")
        )
        scores[neighbor_opinion] += 0.15 * trust

    if not bool(state.get("event", {}).get("verified", False)):
        scores["reject"] += 0.15 * verification
        scores["uncertain"] += 0.15 * risk

    vote = max(scores, key=scores.get)
    vote_confidence = clamp(0.45 + scores[vote] / 2.0)
    return vote, round(vote_confidence, 3)


def _summarize_debate(
    state: dict[str, Any], claims: list[dict[str, Any]], votes: dict[str, Any]
) -> str:
    vote_counts = Counter(vote["vote"] for vote in votes.values())
    majority_vote, majority_count = vote_counts.most_common(1)[0]
    total = max(1, len(votes))
    event = state.get("event", {}).get("content", "当前信息")
    consensus_text = (
        "已形成较明显多数意见"
        if majority_count / total >= 0.6
        else "群体仍存在明显分歧"
    )
    stance_text = "；".join(
        f"{claim['agent_name']}={claim['stance']}({claim['confidence']})"
        for claim in claims
    )
    return (
        f"围绕“{event}”，本轮辩论收集 {len(claims)} 条立场陈述："
        f"{stance_text}。最终投票中，{majority_vote} 获得 "
        f"{majority_count}/{total} 票，{consensus_text}。建议在没有官方证据前"
        "将信息标记为待验证，并降低继续扩散的确定性语气。"
    )


def _recent_messages_for_agent(
    state: dict[str, Any], agent_id: str, timestep: int, window: int = 2
) -> list[dict[str, Any]]:
    return [
        message
        for message in state.get("messages", [])
        if timestep - window <= int(message.get("timestep", timestep)) <= timestep
        and (
            message.get("speaker") == agent_id
            or message.get("receiver") == agent_id
        )
    ]


def _valid_opinion(value: Any) -> str:
    opinion = str(value)
    return opinion if opinion in OPINIONS else "uncertain"

