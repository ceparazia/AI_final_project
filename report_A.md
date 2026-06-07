# A模块报告：Agent调度与仿真主流程

![project流程图（A模块报告和PPT用）](C:\Users\28472\Desktop\人工智能\人工智能project\project流程图（A模块报告和PPT用）.png)

## 1. 模块职责

我负责实现项目中的 Agent 调度与仿真主流程。这个模块的核心目标是搭好整个多智能体社会模拟系统的骨架，使后续的记忆反思模块、辩论评估模块和前端展示模块都能围绕同一个 `state` 数据结构进行开发和测试。

具体来说，我实现了以下功能：

- 初始化待验证事件、Agent 角色配置、人格参数、初始观点、置信度和社交关系矩阵。
- 维护方案中约定的统一 `state` 字典，包括 `event`、`agents`、`messages`、`relationships`、`debate`、`metrics` 和 `timeline`。
- 在每个 timestep 中根据 Agent 性格、信任关系和角色特征选择交互对象。
- 调用 DeepSeek API 生成 Agent 对话消息，并将返回内容校验为统一消息格式。
- 在 API 不可用或返回格式异常时使用 fallback / mock 逻辑，保证课堂项目可以稳定运行。
- 在主循环中依次生成消息、调用 B/C 模块接口或本地 fallback、保存每轮状态快照。
- 输出 `output_A/state_A.json`、逐轮 `state_A_timestep_*.json` 和 `api_usage_A.json`，供我自己和其他组员进行模块自测。

由于 6 月 13 日前四个模块还没有完成最终整合，我在本模块中保留了 B/C 模块的适配器逻辑：如果未来存在 B 的 `update_social_state(state, timestep)` 或 C 的 `update_debate_and_metrics(state, timestep)`，主流程会自动调用这些函数；如果暂时不存在，则使用我写的 fallback 逻辑生成可观察的记忆、观点、关系、辩论和指标变化。

## 2. 代码功能说明

### 2.1 `agent.py`

`agent.py` 负责定义仿真系统的基础状态和 Agent 调度辅助函数。

我在这个文件中定义了默认事件 `DEFAULT_EVENT`，表示“某课程考试形式可能从闭卷调整为开卷，具体安排尚未确认。”这条待验证信息。随后我定义了 4 个 Agent 的初始配置：

- `agent_1`：信息传播者，初始更倾向于相信和传播信息。
- `agent_2`：理性验证者，具有较高的 verification 参数。
- `agent_3`：组织协调者，负责在群体中维持较谨慎的表达。
- `agent_4`：风险敏感者，对未确认信息保持更强的拒绝倾向。

`init_state()` 会创建符合方案 5.1 约定的统一 `state` 字典。这个函数不仅初始化 `event` 和 `agents`，还会创建完整的 `relationships`、空的 `messages`、`debate`、`metrics` 和 `timeline`。

`select_interactions()` 用确定性的随机种子为每个 Agent 选择一个交流对象。选择依据包括 Agent 活跃度、双方信任值、历史互动次数和角色加成。例如，理性验证者更倾向于和相信传闻的人交流，风险敏感者更倾向于提醒没有拒绝传闻的人。

`validate_message()` 负责把 LLM 或 fallback 生成的原始消息校验成统一格式，确保每条消息都包含 `timestep`、`speaker`、`receiver`、`content`、`stance` 和 `confidence`。

`create_timeline_snapshot()` 会在每轮结束后生成摘要快照，记录观点数量、传播率、平均置信度、是否触发辩论、各 Agent 当前状态和本轮消息数量。这个字段主要供前端回放和报告分析使用。

### 2.2 `main.py`

`main.py` 是我这个模块的运行入口。

`run_simulation()` 是主流程函数。它先调用 `init_state()` 初始化系统状态，然后循环执行 5 个 timestep。每一轮中，它会：

1. 调用 `select_interactions()` 选择 Agent 交流对象。
2. 对每一组 speaker/receiver 调用 `generate_message()` 生成消息。
3. 把消息追加到 `state["messages"]`。
4. 调用 `update_social_state_adapter()` 更新记忆、观点和关系。
5. 调用 `update_debate_and_metrics_adapter()` 更新辩论记录和指标。
6. 生成 timeline 快照。
7. 保存当前 timestep 的 JSON 状态文件。

`generate_message()` 会优先调用 DeepSeek API 生成符合角色和上下文的对话内容。为了保证输出结构稳定，我在 prompt 中要求模型只返回 JSON，并且只允许包含 `content`、`stance` 和 `confidence` 三个字段。

如果 API 返回内容不是合法 JSON，`main.py` 会先尝试 `_parse_llm_json()` 直接解析；如果失败，再调用 `_repair_llm_json()` 让模型修复 JSON；如果仍然不能得到合法结构，就用 `_coerce_api_text_to_message()` 从文本中提取立场；如果 API 完全不可用，则使用 `_mock_message()` 按角色生成固定规则的消息。

`main()` 提供命令行入口。当前 README 中的运行方式是：

```text
python scripts_A\main.py
```

默认输出目录是 `output_A/`。

### 2.3 `adapters.py`

`adapters.py` 的作用是把我的主流程和 B/C 未来模块连接起来，同时保证在 B/C 代码还没有完成时，我的模块也可以独立自测。

`update_social_state_adapter()` 会尝试加载以下函数：

- `social_state.update_social_state`
- `memory.update_social_state`

如果这些函数存在，就说明 B 模块已经可以接入，适配器会直接调用 B 的实现。如果不存在，适配器会使用我写的 fallback 逻辑，依次调用 `update_memory()`、`update_opinion()`、`update_relationships()` 和 `update_trusted_agents()`。

`update_debate_and_metrics_adapter()` 会尝试加载以下函数：

- `evaluation.update_debate_and_metrics`
- `debate.update_debate_and_metrics`

如果这些函数存在，就调用 C 模块实现；如果不存在，则使用我写的 fallback 逻辑完成辩论触发、辩论记录、投票结果和指标统计。

这里的 fallback 不是最终替代 B/C 的正式实现，而是为了让我的主流程能独立产出完整结构的 `state`，并让 B/C/D 都能基于同一份数据进行模块自测。

### 2.4 `llm_client.py`

`llm_client.py` 是一个轻量级 DeepSeek API 客户端。

我没有引入额外依赖，而是使用 Python 标准库中的 `urllib.request` 发送请求。`DeepSeekClient.chat()` 会向 DeepSeek 的 OpenAI-compatible API 发送 `chat/completions` 请求，并要求返回 JSON object。

API key 的读取顺序是：

1. 优先读取环境变量 `DEEPSEEK_API_KEY`。
2. 如果环境变量不存在，则读取项目根目录下的 `qmh_API.md`。

由于 `qmh_API.md` 包含本地密钥，我没有把它作为报告代码或项目交付内容粘贴进来。`llm_client.py` 中还实现了 `_sanitize_error()`，当 API 报错中包含类似 `sk-...` 的密钥片段时，会把它替换成 `sk-***`，避免泄露。

### 2.5 `__init__.py`

`__init__.py` 用于标记 `scripts_A` 是一个 Python 包。这样代码既可以用 `python scripts_A\main.py` 直接运行，也可以在未来整合时被其他模块导入。

## 3. 模块自测结果

### 3.1 自测运行方式

我按照 README 中的说明运行模块：

```text
python scripts_A\main.py
```

运行后生成的产物保存在 `output_A/` 目录下：

- `state_A.json`
- `state_A_timestep_0.json`
- `state_A_timestep_1.json`
- `state_A_timestep_2.json`
- `state_A_timestep_3.json`
- `state_A_timestep_4.json`
- `api_usage_A.json`

其中，`state_A_timestep_*.json` 是每一轮结束后的状态快照，`state_A.json` 是第 5 轮结束后的完整状态，`api_usage_A.json` 记录了 API 调用情况。

### 3.2 API 调用情况

`output_A/api_usage_A.json` 中记录的结果如下：

```json
{
  "model": "deepseek-v4-flash",
  "attempted": 20,
  "succeeded": 20,
  "failed": 0,
  "errors": [],
  "repair_attempted": 4,
  "repair_succeeded": 0,
  "coerced_from_text": 4,
  "fallback_used": false
}
```

我在自测中一共进行了 20 次消息生成尝试，对应 5 个 timestep 中每轮 4 个 Agent 各发送 1 条消息。20 次调用全部成功，没有出现 API 请求失败。由于有 4 次返回内容需要进一步整理，代码进行了 4 次 JSON repair 尝试，并最终通过文本转换逻辑将 4 条内容转换成统一消息格式。

这说明我的消息生成流程能够处理 LLM 输出格式不完全稳定的问题。即使模型没有严格返回预期 JSON，主流程仍然可以把内容整理为项目统一要求的 `message` 字段结构。

### 3.3 状态输出统计

`output_A/state_A.json` 中的核心统计如下：

- Agent 数量：4
- timestep 数量：5
- message 数量：20
- 每轮消息数量：4
- debate 是否触发：True
- debate round：5
- claims 数量：20
- consensus_reached：False

每轮传播率如下：

```text
timestep 0: spread_rate = 0.25
timestep 1: spread_rate = 0.25
timestep 2: spread_rate = 0.25
timestep 3: spread_rate = 0.25
timestep 4: spread_rate = 0.25
```

每轮平均置信度如下：

```text
timestep 0: average_confidence = 0.613
timestep 1: average_confidence = 0.628
timestep 2: average_confidence = 0.627
timestep 3: average_confidence = 0.65
timestep 4: average_confidence = 0.62
```

每轮观点数量如下：

```text
timestep 0: believe = 1, reject = 1, uncertain = 2
timestep 1: believe = 1, reject = 1, uncertain = 2
timestep 2: believe = 1, reject = 1, uncertain = 2
timestep 3: believe = 1, reject = 1, uncertain = 2
timestep 4: believe = 1, reject = 1, uncertain = 2
```

最后一轮的 Agent 状态如下：

```text
agent_1: opinion = believe, confidence = 0.71, trusted_agents = []
agent_2: opinion = uncertain, confidence = 0.46, trusted_agents = []
agent_3: opinion = uncertain, confidence = 0.46, trusted_agents = ["agent_2"]
agent_4: opinion = reject, confidence = 0.85, trusted_agents = []
```

### 3.4 自测结果分析

从模块自测结果可以看到，我的主流程成功完成了 5 轮仿真，并且每一轮都生成了 4 条 Agent 对话消息，因此调度逻辑和消息生成逻辑能够正常运行。

观点分布始终保持为 1 个 believe、1 个 reject 和 2 个 uncertain。这说明在当前 fallback 和 API 输出共同作用下，群体没有快速形成一致意见，而是维持了争议状态。这与项目设定中的“校园争议信息传播”场景是匹配的：信息传播者倾向于相信和提醒别人，风险敏感者倾向于拒绝，理性验证者和组织协调者保持谨慎。

`debate_triggered` 为 True，并且 5 轮中累计产生了 20 条 claims，说明辩论触发和辩论记录字段可以正常写入。由于每轮都存在 believe 和 reject 的立场冲突，fallback 辩论逻辑会持续记录不同 Agent 的观点和投票。

`consensus_reached` 为 False，说明当前模块自测没有形成群体共识。这不是错误，而是符合这个自测场景：待验证信息没有官方确认，Agent 的性格和角色设置会让系统保留分歧。

最后一轮中，`agent_3` 的 `trusted_agents` 包含 `agent_2`，说明关系更新和信任对象更新逻辑已经产生了可观察变化。`agent_2` 作为理性验证者，在当前规则下更容易被组织协调者信任，这也符合角色设定。

综上，我的模块已经能够独立生成符合统一字段约定的 mock/fallback 状态，能够为 B、C、D 模块提供自测数据。这里的结果是模块自测结果，不是四人代码整合后的最终项目结果。

## 4. A模块全部代码

### 4.1 `scripts_A/__init__.py`

```python
"""A module for the AlTown simulation scheduler."""
```

### 4.2 `scripts_A/agent.py`

```python
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
```

### 4.3 `scripts_A/adapters.py`

```python
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
```

### 4.4 `scripts_A/llm_client.py`

```python
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SECRET_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]+")


@dataclass
class LLMResult:
    content: str
    used_api: bool
    error: str | None = None


class DeepSeekClient:
    """Small dependency-free client for DeepSeek's OpenAI-compatible API."""

    def __init__(
        self,
        model: str = "deepseek-v4-flash",
        base_url: str = "https://api.deepseek.com",
        timeout: int = 25,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = load_api_key()

    def chat(self, messages: list[dict[str, str]], temperature: float = 0.45) -> LLMResult:
        if not self.api_key:
            return LLMResult("", False, "DEEPSEEK_API_KEY is not available")

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
            "stream": False,
        }
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            return LLMResult("", False, _sanitize_error(f"HTTP {exc.code}: {detail}"))
        except Exception as exc:  # noqa: BLE001 - keep fallback robust for classroom demos.
            return LLMResult("", False, _sanitize_error(str(exc)))

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            return LLMResult("", False, _sanitize_error(f"Unexpected response: {data!r}"))

        return LLMResult(str(content).strip(), True, None)


def load_api_key() -> str | None:
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        return env_key.strip()

    local_key_path = Path(__file__).resolve().parents[1] / "qmh_API.md"
    if not local_key_path.exists():
        return None

    text = local_key_path.read_text(encoding="utf-8").strip()
    match = SECRET_PATTERN.search(text)
    if match:
        return match.group(0)
    return text or None


def _sanitize_error(text: str) -> str:
    return SECRET_PATTERN.sub("sk-***", text)
```

### 4.5 `scripts_A/main.py`

```python
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
    output_path = Path(output_dir) if output_dir else PROJECT_ROOT/"output_A"
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
    parser.add_argument("--output-dir", default=str(PROJECT_ROOT/ "output_A"), help="directory for state_A outputs")
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
```
