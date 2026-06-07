from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

try:
    from .adapters import update_debate_and_metrics_adapter, update_social_state_adapter
    from .agent import create_timeline_snapshot, init_state, save_state, select_interactions as agent_select
    from .agent import validate_message
    from .llm_client import DeepSeekClient
except ImportError:  # pragma: no cover - supports `python scripts_A/main.py`.
    from adapters import update_debate_and_metrics_adapter, update_social_state_adapter
    from agent import create_timeline_snapshot, init_state, save_state, select_interactions as agent_select
    from agent import validate_message
    from llm_client import DeepSeekClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def select_interactions(state: dict[str, Any], timestep: int) -> list[tuple[str, str]]:
    return agent_select(state, timestep)


def generate_message(
    state: dict[str, Any],
    speaker_id: str,
    receiver_id: str,
    timestep: int,
    client: DeepSeekClient | None = None,
    api_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a shared-format message through DeepSeek, with mock fallback."""
    client = client or DeepSeekClient()
    api_stats = api_stats if api_stats is not None else {
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
        "repair_attempted": 0,
        "repair_succeeded": 0,
    }
    api_stats["attempted"] += 1

    prompt_messages = _build_prompt_messages(state, speaker_id, receiver_id, timestep)
    result = client.chat(prompt_messages)
    if result.used_api:
        parsed = _parse_llm_json(result.content)
        if parsed:
            api_stats["succeeded"] += 1
            return validate_message(state, parsed, speaker_id, receiver_id, timestep)
        repaired = _repair_llm_json(client, result.content, api_stats)
        if repaired:
            api_stats["succeeded"] += 1
            return validate_message(state, repaired, speaker_id, receiver_id, timestep)
        coerced = _coerce_api_text_to_message(state, speaker_id, result.content)
        api_stats["succeeded"] += 1
        api_stats["coerced_from_text"] = api_stats.get("coerced_from_text", 0) + 1
        return validate_message(state, coerced, speaker_id, receiver_id, timestep)
    else:
        api_stats["failed"] += 1
        if result.error:
            api_stats["errors"].append(result.error)

    return validate_message(state, _mock_message(state, speaker_id, receiver_id, timestep), speaker_id, receiver_id, timestep)


def run_simulation(T: int = 5, output_dir: str | Path | None = None) -> dict[str, Any]:
    output_path = Path(output_dir) if output_dir else PROJECT_ROOT/"output"
    state = init_state()
    client = DeepSeekClient()
    api_stats: dict[str, Any] = {
        "model": client.model,
        "attempted": 0,
        "succeeded": 0,
        "failed": 0,
        "errors": [],
        "repair_attempted": 0,
        "repair_succeeded": 0,
        "coerced_from_text": 0,
        "fallback_used": False,
    }

    for timestep in range(T):
        interactions = select_interactions(state, timestep)
        for speaker_id, receiver_id in interactions:
            message = generate_message(state, speaker_id, receiver_id, timestep, client, api_stats)
            state["messages"].append(message)

        state = update_social_state_adapter(state, timestep)
        state = update_debate_and_metrics_adapter(state, timestep)
        state["timeline"].append(create_timeline_snapshot(state, timestep))
        save_state(state, output_path / f"state_A_timestep_{timestep}.json")

    api_stats["fallback_used"] = api_stats["failed"] > 0
    api_stats["errors"] = sorted(set(api_stats["errors"]))[:5]
    save_state(state, output_path / "state_A.json")
    _write_json(api_stats, output_path / "api_usage_A.json")
    return state


def _build_prompt_messages(
    state: dict[str, Any],
    speaker_id: str,
    receiver_id: str,
    timestep: int,
) -> list[dict[str, str]]:
    speaker = state["agents"][speaker_id]
    receiver = state["agents"][receiver_id]
    recent_messages = state["messages"][-6:]
    relation = state["relationships"].get(speaker_id, {}).get(receiver_id, {"trust": 0.55})

    context = {
        "event": state["event"],
        "timestep": timestep,
        "speaker": {
            "id": speaker_id,
            "name": speaker["name"],
            "role": speaker["role"],
            "personality": speaker["personality"],
            "opinion": speaker["opinion"],
            "confidence": speaker["confidence"],
        },
        "receiver": {
            "id": receiver_id,
            "name": receiver["name"],
            "role": receiver["role"],
            "opinion": receiver["opinion"],
            "confidence": receiver["confidence"],
        },
        "relationship": relation,
        "recent_messages": recent_messages,
    }

    return [
        {
            "role": "system",
            "content": (
                "You are simulating one concise campus-community AI agent message. "
                "Return strict json only. The only valid format is "
                '{"content":"...","stance":"uncertain","confidence":0.5}. '
                "Keys must be content, stance, confidence. "
                "stance must be one of believe, reject, uncertain. confidence is 0.0-1.0. "
                "Do not use Markdown, code fences, explanations, or extra text. "
                "Do not mention that you are an AI model."
            ),
        },
        {
            "role": "user",
            "content": (
                "请根据下面的状态，生成 speaker 对 receiver 说的一句话。"
                "语气要符合角色，内容围绕待验证信息，不要超过 70 个中文字符。"
                "只输出一个 json object，格式必须类似："
                '{"content":"一句话","stance":"uncertain","confidence":0.5}。'
                "不要输出 Markdown、解释或代码块。\n"
                f"{json.dumps(context, ensure_ascii=False)}"
            ),
        },
    ]


def _parse_llm_json(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return None
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(parsed, dict):
        return None
    return parsed


def _repair_llm_json(
    client: DeepSeekClient,
    raw_content: str,
    api_stats: dict[str, Any],
) -> dict[str, Any] | None:
    api_stats["repair_attempted"] += 1
    repair_messages = [
        {
            "role": "system",
            "content": (
                "Convert the user's text into strict json only. "
                "The json object must have exactly these keys: content, stance, confidence. "
                "stance must be believe, reject, or uncertain. confidence must be 0.0-1.0. "
                "Return no Markdown and no explanation."
            ),
        },
        {
            "role": "user",
            "content": (
                "把下面内容转换为合法 json object。只输出 json：\n"
                f"{raw_content}"
            ),
        },
    ]
    repair_result = client.chat(repair_messages, temperature=0.0)
    if not repair_result.used_api:
        if repair_result.error:
            api_stats["errors"].append(f"JSON repair failed: {repair_result.error}")
        return None

    parsed = _parse_llm_json(repair_result.content)
    if parsed:
        api_stats["repair_succeeded"] += 1
        return parsed
    return None


def _coerce_api_text_to_message(
    state: dict[str, Any],
    speaker_id: str,
    raw_content: str,
) -> dict[str, Any]:
    content = re.sub(r"```(?:json)?|```", "", raw_content).strip()
    content = re.sub(r"\s+", " ", content)
    if len(content) > 120:
        content = content[:117] + "..."
    if not content:
        content = "这条信息还需要等待正式通知确认。"

    lowered = content.lower()
    if any(word in lowered for word in ["不相信", "不要相信", "reject", "风险", "未确认", "核实", "证据"]):
        stance = "reject"
    elif any(word in lowered for word in ["相信", "believe", "可以传播", "分享"]):
        stance = "believe"
    else:
        stance = state["agents"][speaker_id].get("opinion", "uncertain")
        if stance not in {"believe", "reject", "uncertain"}:
            stance = "uncertain"

    confidence = max(0.5, min(0.85, float(state["agents"][speaker_id].get("confidence", 0.6))))
    return {
        "content": content,
        "stance": stance,
        "confidence": confidence,
    }


def _mock_message(state: dict[str, Any], speaker_id: str, receiver_id: str, timestep: int) -> dict[str, Any]:
    speaker = state["agents"][speaker_id]
    receiver_name = state["agents"][receiver_id]["name"]
    event = state["event"]["content"]
    role = speaker["role"]

    if role == "active_spreader":
        return {
            "content": f"{receiver_name}，我听到“{event}”，可以先提醒大家留意，但我也会标注未确认。",
            "stance": "believe",
            "confidence": 0.62 + 0.02 * min(timestep, 3),
        }
    if role == "rational_verifier":
        return {
            "content": f"{receiver_name}，这条消息还没有正式来源，我建议先查课程通知再决定是否传播。",
            "stance": "reject" if timestep >= 1 else "uncertain",
            "confidence": 0.68 + 0.03 * min(timestep, 2),
        }
    if role == "coordinator":
        return {
            "content": f"{receiver_name}，我们先把信息记录下来，对外统一说“尚未确认，等待正式通知”。",
            "stance": "uncertain",
            "confidence": 0.64,
        }
    return {
        "content": f"{receiver_name}，如果直接按开卷准备会有风险，我倾向于先不要相信这条传闻。",
        "stance": "reject",
        "confidence": 0.72 + 0.02 * min(timestep, 2),
    }


def _write_json(data: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run A student's AlTown simulation scheduler.")
    parser.add_argument("--rounds", type=int, default=5, help="number of timesteps")
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT/ "output"), help="directory for state_A outputs")
    args = parser.parse_args()

    state = run_simulation(T=args.rounds, output_dir=args.output_dir)
    counts = state["timeline"][-1]["opinion_count"] if state["timeline"] else {}
    print(
        "A simulation complete: "
        f"messages={len(state['messages'])}, "
        f"timeline={len(state['timeline'])}, "
        f"final_opinions={counts}"
    )


if __name__ == "__main__":
    main()
