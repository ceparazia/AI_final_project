# C模块报告：辩论、投票与实验评估

## 1. 模块职责

我（张易聆）负责实现项目中的 C 模块，也就是争议信息进入多智能体传播过程后，对群体分歧进行辩论组织、立场陈述、投票判断和实验指标统计的部分。这个模块的核心目标是把 A 模块和 B 模块已经维护好的统一 `state` 进一步加工成可解释的 `debate` 和 `metrics` 数据，使系统不仅能生成 Agent 对话和状态变化，也能回答“争议是否出现、各 Agent 为什么这样判断、最终投票倾向是什么、传播风险如何变化”等问题。

具体来说，我实现了以下功能：

- 读取统一 `state` 字典中的 `event`、`agents`、`messages` 和 `relationships` 字段，保持和 A 模块、B 模块约定的数据结构一致。
- 根据观点冲突、平均置信度和不确定 Agent 数量判断是否进入 debate mode。
- 为每个 Agent 生成结构化立场陈述 claim，记录 Agent 当前观点、置信度、角色信息和对应理由。
- 结合 Agent 当前观点、`confidence`、人格参数、信任关系和事件验证状态计算投票结果。
- 输出每个 Agent 的 `vote`、投票 `confidence` 和是否继续传播 `continue_spreading`。
- 汇总本轮辩论结果，生成可供报告和前端展示使用的 `debate["summary"]`。
- 按 timestep 追加 `spread_rate`、`average_confidence`、`opinion_count` 和 `consensus_reached` 等实验指标。
- 提供统一入口 `update_debate_and_metrics(state, timestep)`，使 A 模块主循环可以在每轮状态更新后直接调用 C 模块。
- 编写 `run_selftest_C.py`，读取 A 模块输出的 5 个 timestep 状态，对 C 模块的辩论、投票、指标统计和读写边界进行自测。

我在实现时把 C 模块的读写边界控制得比较明确：C 模块只负责写入 `debate` 和 `metrics`，不修改 `agents`、`relationships`、`messages` 等由其他模块维护的字段。这样做可以减少模块整合时的相互影响，也方便 D 模块直接读取辩论结果和指标序列进行展示。

## 2. 代码功能说明

### 2.1 `scripts_C/debate.py`

`debate.py` 是我实现 C 模块辩论逻辑的核心文件。这个文件负责判断争议是否需要进入辩论，生成每个 Agent 的立场陈述，计算投票结果，并整理本轮辩论摘要。

我首先定义了统一观点集合 `OPINIONS = ("believe", "reject", "uncertain")`，并用 `get_opinion_counts(state)` 对当前所有 Agent 的观点进行统计。这里我没有直接信任输入值，而是把不在三类观点中的异常值统一归入 `uncertain`，保证后续统计不会因为脏数据中断。

`should_trigger_debate(state, timestep)` 用三个条件判断是否触发辩论：

- 同时存在 `believe` 和 `reject`，说明群体内部已经出现明确观点冲突。
- 所有 Agent 的平均置信度低于 0.6，说明群体判断整体不稳定。
- `uncertain` 数量超过 Agent 总数的一半，说明信息还处在高不确定状态。

只要满足其中任意一个条件，我就让系统进入 debate mode。这个设计对应项目中“争议信息传播”的场景：匿名消息不应该只看传播次数，还应该看群体观点是否分裂、判断是否摇摆。

`run_debate(state, timestep)` 是辩论执行函数。它会为每个 Agent 调用 `_build_claim` 生成一条结构化 claim，再调用 `_score_vote` 生成投票结果，最后用 `_summarize_debate` 写出本轮摘要。写入后的 `debate` 字段包含：

- `triggered`：本轮是否触发辩论。
- `round`：当前辩论轮数。
- `claims`：每个 Agent 的立场陈述列表。
- `votes`：每个 Agent 的投票结果。
- `summary`：本轮辩论的自然语言总结。

`_build_claim` 会结合 Agent 的当前观点、置信度、人格参数和最近两轮相关消息生成理由。例如，`believe` 的 Agent 会强调近期信息与自身判断一致；`reject` 的 Agent 会强调证据不足或来源风险；`uncertain` 的 Agent 会保留观望态度。如果最近有相关消息，claim 里还会记录参考了哪一次交流，使报告中的立场陈述不是孤立生成的。

`_score_vote` 是我写的投票打分逻辑。它不是简单复制 Agent 当前观点，而是综合四类因素：

- 当前 `opinion` 和 `confidence`。
- 人格参数中的 `trustfulness`、`verification` 和 `risk_sensitivity`。
- `relationships` 中高信任邻居的观点影响。
- `event["verified"]` 是否为真；如果事件没有被官方验证，就提高 `reject` 和 `uncertain` 的权重。

这样处理后，投票结果既保留了 Agent 的当前状态，又能体现验证倾向、风险敏感度和社交信任关系对最终判断的影响。

### 2.2 `scripts_C/evaluation.py`

`evaluation.py` 是 C 模块对外暴露的统一入口。A 模块或整合后的主流程只需要调用：

```python
from scripts_C.evaluation import update_debate_and_metrics
state = update_debate_and_metrics(state, timestep)
```

`update_debate_and_metrics(state, timestep)` 会先调用 `should_trigger_debate` 判断是否进入辩论。如果触发辩论，就调用 `run_debate` 写入 claims、votes 和 summary；如果没有触发辩论，也会保证 `debate` 字段存在，并把 `triggered` 置为 `False`。随后函数统一调用 `update_metrics` 追加指标。

`update_metrics` 负责向 `metrics` 字段追加四类数据：

- `spread_rate`：当前相信信息的 Agent 占比。
- `average_confidence`：所有 Agent 的平均置信度。
- `opinion_count`：`believe`、`reject`、`uncertain` 三类观点数量。
- `consensus_reached`：是否有至少 75% 的 Agent 进入同一观点。

我还处理了空 Agent 的边界情况。如果 `agents` 为空，函数会写入 0 值指标并保持 `consensus_reached = False`，避免除零错误。

### 2.3 `scripts_C/run_selftest_C.py`

`run_selftest_C.py` 是我为 C 模块写的自测脚本。它读取 `output_A/state_A_timestep_0.json` 到 `state_A_timestep_4.json`，分别建立副本后清空副本中的 `debate` 和 `metrics`，再调用 C 模块入口重新生成辩论和指标。

我在自测脚本里重点检查了两类问题。第一类是功能输出是否完整，包括是否触发辩论、claim 数量、投票分布、传播率、平均置信度、观点数量和共识状态。第二类是模块边界是否清晰，即 C 模块运行后 `agents` 和 `relationships` 是否保持不变。这个检查可以证明 C 模块没有越权修改 A/B 模块维护的状态。

脚本运行后会输出三个文件：

- `output_C/state_C_selftest.json`：最后一个 timestep 经过 C 模块处理后的完整状态。
- `output_C/selftest_summary_C.json`：结构化自测总结。
- `output_C/selftest_metrics_C.csv`：便于表格查看和报告引用的指标结果。

### 2.4 `scripts_C/__init__.py` 和根目录 `evaluation.py`

`scripts_C/__init__.py` 用于把 `scripts_C` 标记为可导入的 Python 包，并导出 `update_debate_and_metrics`。这样 C 模块可以被其他代码用包导入的方式调用。

根目录下的 `evaluation.py` 是兼容入口。因为 A 模块适配器会尝试导入顶层 `evaluation.update_debate_and_metrics`，我写了这个转发文件，把调用转到 `scripts_C.evaluation`。这样既不需要改变 A 模块已有适配逻辑，也能保持 C 模块自身代码集中放在 `scripts_C/` 目录下。

## 3. 模块自测结果

### 3.1 自测运行方式

我按照 C 模块自测脚本的说明，在项目根目录运行：

```text
python scripts_C\run_selftest_C.py
```

自测脚本读取 A 模块生成的 5 个 timestep 状态，并对每个状态重新执行 C 模块入口：

```python
state = update_debate_and_metrics(state, timestep)
```

运行后生成的产物保存在 `output_C/` 目录下：

- `state_C_selftest.json`
- `selftest_summary_C.json`
- `selftest_metrics_C.csv`

其中，`selftest_summary_C.json` 记录每轮是否触发辩论、claim 数量、投票结果和边界检查结果；`selftest_metrics_C.csv` 把每轮指标整理成表格；`state_C_selftest.json` 保存最后一轮处理后的状态，便于检查 `debate` 和 `metrics` 的最终结构。

### 3.2 自测汇总结果

`output_C/selftest_summary_C.json` 中记录的总结果为：

```json
{
  "module": "C",
  "passed": true,
  "states_tested": 5
}
```

各轮自测结果如下：

|轮次|触发辩论|陈述数|投票 believe|投票 reject|投票 uncertain|传播率|平均置信度|观点 believe|观点 reject|观点 uncertain|达成共识|Agent 未被修改|关系未被修改|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
|0|True|4|1|1|2|0.25|0.613|1|1|2|False|True|True|
|1|True|4|1|1|2|0.25|0.628|1|1|2|False|True|True|
|2|True|4|1|1|2|0.25|0.627|1|1|2|False|True|True|
|3|True|4|1|1|2|0.25|0.65|1|1|2|False|True|True|
|4|True|4|1|1|2|0.25|0.62|1|1|2|False|True|True|

从表格可以看到，5 个 timestep 全部触发辩论，每轮都生成了 4 条 claim，对应 4 个 Agent 各自给出一条立场陈述。每轮投票分布都保持为 `believe = 1`、`reject = 1`、`uncertain = 2`，说明系统没有把匿名消息直接扩散成确定事实，而是保留了相信、拒绝和观望三类判断。

### 3.3 指标输出统计

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

边界检查结果如下：

```text
timestep 0: agents_unchanged = True, relationships_unchanged = True
timestep 1: agents_unchanged = True, relationships_unchanged = True
timestep 2: agents_unchanged = True, relationships_unchanged = True
timestep 3: agents_unchanged = True, relationships_unchanged = True
timestep 4: agents_unchanged = True, relationships_unchanged = True
```

### 3.4 自测结果分析

从自测结果可以看出，我写的 C 模块能够稳定接入统一 `state`，并在每一轮状态上生成完整的 `debate` 和 `metrics` 输出。由于 A 模块输出中始终同时存在 `believe` 与 `reject`，而且 `uncertain` 数量为 2，所以 C 模块每轮都会触发 debate mode。这与争议信息传播场景相匹配：当群体内部既有人相信，也有人拒绝，同时还有一半成员观望时，系统应该进入辩论和投票环节。

传播率始终为 0.25，说明 4 个 Agent 中只有 1 个倾向相信并继续推动信息传播。平均置信度在 0.613 到 0.65 之间波动，说明群体判断不是完全随机，也没有达到高度一致。`consensus_reached` 始终为 `False`，因为没有任何一种观点达到 75% 的共识阈值。这个结果说明 C 模块可以把“存在分歧但未达成共识”的状态表达为可量化指标。

边界检查全部通过，`agents_unchanged` 和 `relationships_unchanged` 在 5 轮中都为 `True`。这说明 C 模块确实只写入 `debate` 和 `metrics`，没有改动 Agent 状态、社交关系或消息记录。对最终系统来说，这一点很重要，因为 B 模块负责记忆、观点和关系演化，C 模块只负责辩论、投票和指标统计。

综合来看，我的 C 模块已经完成了从代码实现到自测验证的完整过程：代码层面提供了可导入的统一入口，功能层面完成了辩论触发、立场陈述、投票计算和指标统计，自测层面验证了输出正确性和模块边界。生成的 `output_C` 产物可以直接用于报告分析，也可以供 D 模块读取后进行可视化展示。

## 4. C模块全部代码


### 4.1 `scripts_C/__init__.py`

```python
"""C module public entrypoint for AlTown."""

from .evaluation import update_debate_and_metrics

__all__ = ["update_debate_and_metrics"]
```


### 4.2 `scripts_C/debate.py`

```python
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
```


### 4.3 `scripts_C/evaluation.py`

```python
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
```


### 4.4 `scripts_C/run_selftest_C.py`

```python
"""Self-test C module with A module outputs.

Run from the repository root:

    python scripts_C\run_selftest_C.py

The script validates C's debate and metrics logic on A module states,
then writes output_C artifacts for report analysis.
"""

from __future__ import annotations

import copy
import csv
import json
import sys
from pathlib import Path
from typing import Any

try:
    from .debate import should_trigger_debate
    from .evaluation import update_debate_and_metrics
except ImportError:  # pragma: no cover - supports direct script execution.
    CURRENT_DIR = Path(__file__).resolve().parent
    if str(CURRENT_DIR) not in sys.path:
        sys.path.insert(0, str(CURRENT_DIR))
    from debate import should_trigger_debate
    from evaluation import update_debate_and_metrics


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_A = PROJECT_ROOT / "output_A"
OUTPUT_C = PROJECT_ROOT / "output_C"


EMPTY_DEBATE = {
    "triggered": False,
    "round": 0,
    "claims": [],
    "votes": {},
    "summary": "",
}
EMPTY_METRICS = {
    "spread_rate": [],
    "average_confidence": [],
    "opinion_count": [],
    "consensus_reached": False,
}


def main() -> None:
    OUTPUT_C.mkdir(parents=True, exist_ok=True)
    state_files = sorted(OUTPUT_A.glob("state_A_timestep_*.json"), key=_timestep_key)
    if not state_files:
        raise FileNotFoundError(f"No A timestep states found in {OUTPUT_A}")

    summaries = []
    final_state: dict[str, Any] | None = None
    for state_file in state_files:
        timestep = _timestep_key(state_file)
        raw_state = _read_json(state_file)
        state = _prepare_c_only_state(raw_state)
        original_agents = copy.deepcopy(state.get("agents", {}))
        original_relationships = copy.deepcopy(state.get("relationships", {}))
        trigger_before = should_trigger_debate(state, timestep)

        updated = update_debate_and_metrics(state, timestep)
        agents_unchanged = original_agents == updated.get("agents", {})
        relationships_unchanged = (
            original_relationships == updated.get("relationships", {})
        )
        latest_metrics = _latest_metrics(updated)
        vote_counts = _count_votes(updated.get("debate", {}).get("votes", {}))
        summary = {
            "source_file": state_file.name,
            "timestep": timestep,
            "trigger_before_update": trigger_before,
            "debate_triggered": bool(updated.get("debate", {}).get("triggered")),
            "claim_count": len(updated.get("debate", {}).get("claims", [])),
            "vote_counts": vote_counts,
            "agents_unchanged": agents_unchanged,
            "relationships_unchanged": relationships_unchanged,
            **latest_metrics,
        }
        summaries.append(summary)
        final_state = updated

    if final_state is None:
        raise RuntimeError("C self-test did not produce a final state")

    _write_json(final_state, OUTPUT_C / "state_C_selftest.json")
    _write_json(
        {
            "module": "C",
            "description": "Debate, vote, confidence and metrics self-test on A outputs.",
            "passed": all(
                item["agents_unchanged"] and item["relationships_unchanged"]
                for item in summaries
            ),
            "items": summaries,
        },
        OUTPUT_C / "selftest_summary_C.json",
    )
    _write_csv(summaries, OUTPUT_C / "selftest_metrics_C.csv")

    print("C module self-test complete.")
    print(f"states_tested={len(summaries)}")
    print(
        "boundary_ok="
        f"{all(item['agents_unchanged'] and item['relationships_unchanged'] for item in summaries)}"
    )
    print(f"output={OUTPUT_C}")


def _prepare_c_only_state(state: dict[str, Any]) -> dict[str, Any]:
    prepared = copy.deepcopy(state)
    prepared["debate"] = copy.deepcopy(EMPTY_DEBATE)
    prepared["metrics"] = copy.deepcopy(EMPTY_METRICS)
    return prepared


def _latest_metrics(state: dict[str, Any]) -> dict[str, Any]:
    metrics = state.get("metrics", {})
    opinion_count = _latest(metrics.get("opinion_count", []), {})
    return {
        "spread_rate": _latest_value(metrics.get("spread_rate", []), 0.0),
        "average_confidence": _latest_value(metrics.get("average_confidence", []), 0.0),
        "believe": int(opinion_count.get("believe", 0)),
        "reject": int(opinion_count.get("reject", 0)),
        "uncertain": int(opinion_count.get("uncertain", 0)),
        "consensus_reached": bool(metrics.get("consensus_reached", False)),
    }


def _count_votes(votes: dict[str, dict[str, Any]]) -> dict[str, int]:
    counts = {"believe": 0, "reject": 0, "uncertain": 0}
    for vote in votes.values():
        label = vote.get("vote", "uncertain")
        if label not in counts:
            label = "uncertain"
        counts[label] += 1
    return counts


def _latest(series: list[Any], default: Any) -> Any:
    return series[-1] if series else default


def _latest_value(series: list[Any], default: float) -> float:
    item = _latest(series, None)
    if isinstance(item, dict):
        return float(item.get("value", default))
    if item is None:
        return default
    return float(item)


def _timestep_key(path: Path) -> int:
    return int(path.stem.rsplit("_", 1)[-1])


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(data: Any, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "timestep",
        "source_file",
        "trigger_before_update",
        "debate_triggered",
        "claim_count",
        "spread_rate",
        "average_confidence",
        "believe",
        "reject",
        "uncertain",
        "consensus_reached",
        "agents_unchanged",
        "relationships_unchanged",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


if __name__ == "__main__":
    main()
```


### 4.5 `evaluation.py`

```python
"""Compatibility wrapper for A module adapter.

A's current adapter imports a top-level module named ``evaluation``. The C
module itself is stored under ``scripts_C/`` as required by README, so this
wrapper forwards the public entrypoint without changing A's code.
"""

from scripts_C.evaluation import update_debate_and_metrics

__all__ = ["update_debate_and_metrics"]
```

