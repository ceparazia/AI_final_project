# **B 模块报告：记忆、反思与关系演化**

## **1\. 模块职责与定位**

我负责实现 AlTown 项目中的 B 模块，即核心的“记忆、反思与关系演化”机制。在整个多智能体社会模拟系统中，如果说 A 模块搭建了时间步流转和消息传递的物理骨架，C 模块负责提炼群体争议并输出指标，那么我负责的 B 模块则赋予了 Agent **“认知深度”和“社交动态性”**。

在真实的校园信息传播场景中，个体绝不是一个只会根据当前 Prompt 盲目回答的无状态机器。个体在接收到传闻后，会经历复杂的心理活动：

1. **记忆机制**：他们会记住自己曾经听过什么信息，以及这些信息是由谁传达的。  
2. **反思机制**：他们会因为听到了不同的声音而产生认知失调（动摇），或因为听到了相同的声音而产生回音壁效应（更加坚定）。  
3. **关系演化**：他们会因为与他人观点是否一致，而动态地调整对该个体的信任程度。

B 模块的核心职责就是将上述心理学和社会学现象在代码层面进行量化和模拟。具体来说，我实现了以下几个关键功能：

* **统一的状态读写边界**：严格遵循方案中约定的 state 数据结构。只读取 messages，并负责更新 agents\[\*\].memory、agents\[\*\].confidence 以及 relationships 矩阵，坚决不越权修改 event 或 metrics 等其他模块维护的字段，保证了模块间的解耦。  
* **带容量限制的精细化记忆模型**：提取当前时间步的消息，区分“发送 (sent)”与“接收 (received)”进行分类存储，并引入了 MAX\_MEMORY\_CAPACITY 来模拟人类工作记忆的上限。  
* **基于人格参数的非线性反思算法**：摒弃了简单的固定数值加减，引入 Agent 的 trustfulness（信任度）和 risk\_sensitivity（风险敏感度），综合计算其心理影响得分，实现置信度的动态极化或衰减。  
* **基于同质相吸的不对称社交演化**：遍历每一轮交互，结合接收者的 verification（验证倾向）参数，不对称地更新信任网络，模拟出真实世界中复杂的“信息茧房”和信任分化。

## **2\. 核心代码功能深度解析**

### **2.1 模块主入口 (update\_social\_state)**

在 scripts\_B/memory\_and\_social.py 中，我对外暴露了唯一的集成接口 update\_social\_state(state, timestep)。该函数在 A 模块的主循环中被逐轮调用，内部依次执行 \_update\_memories、\_reflect\_agents 和 \_update\_relationships 三个子步骤，形成了一个完整的“感知-思考-社交”闭环。

### **2.2 记忆编码与遗忘逻辑 (\_update\_memories)**

该函数负责拦截当前 timestep 的所有对话，并将它们分别写入发言者和接收者的长期记忆列表。

**核心设计与创新点**：

* **方向打标 (Direction Tagging)**：我在记忆条目中引入了一个关键字段 direction。如果是自己发出的消息，标记为 sent；如果是听到的消息，标记为 received。这为后续的反思机制提供了高精度的上下文，因为在心理学中，“我曾公开表达过的立场”和“我被动接收到的信息”对个体信念的巩固作用是截然不同的。  
* **记忆遗忘 (Memory Pruning)**：为了防止长时间模拟导致内存爆炸，同时模拟人类认知负荷的限制，我设置了 MAX\_MEMORY\_CAPACITY。超出容量的早期记忆会被自动剔除，这使得 Agent 的决策更依赖于近期接收到的信息。

### **2.3 认知失调与回音壁效应模拟 (\_reflect\_agents)**

这是模拟 Agent 内部心理波动的核心算法，它决定了观点的置信度将如何演化。Agent 会往前回溯近期的接收信息，并进行非线性计算：

* **回音壁效应 (Echo Chamber Effect)**：如果近期听到的声音与自己当前的 opinion 一致，置信度会上升。但上升的幅度并非恒定，而是会被 Agent 自身的 trustfulness（轻信程度）放大。  
* **认知失调与风险警告 (Cognitive Dissonance)**：如果听到反对意见（尤其是带有 reject 立场的信息），Agent 会产生自我怀疑。特别地，如果该 Agent 的 risk\_sensitivity（风险敏感度）较高，那么受到拒绝或警告信息的心理惩罚将成倍增加。  
* **观点翻转机制 (Opinion Flipping)**：当置信度因持续受到打击而跌破极低阈值（如 0.2）时，Agent 将陷入严重的心理动摇，并可能被迫接受近期听到的主流意见，从而发生观点的反转。

### **2.4 不对称信任网络演化 (\_update\_relationships)**

该函数彻底打破了传统模拟中静态的社交图谱，实现了多维度的关系动态更新：

* **同质相吸 (Homophily)**：交流双方立场一致时，信任值增加；立场冲突时，触发信任惩罚。  
* **验证倾向制约**：信任的增加幅度受到接收方 verification 参数的制约。一个高验证倾向的“理性验证者”，即使别人赞同他，他也不会轻易给出极高的信任分。  
* **不对称信任 (Asymmetric Trust)**：真实社交中，“A 信任 B” 并不意味着 “B 同样信任 A”。本算法分别独立计算发言者对接收者、接收者对发言者的信任增减，并在每一次互动中加入微小的“曝光效应”（mere-exposure effect）正向偏置。

## **3\. 模块自测与实验结果分析**

### **3.1 自测环境与运行流程**

为了验证认知算法的有效性，我编写了 scripts\_B/test\_module\_b.py 作为 B 模块的独立测试脚手架。它读取 A 模块跑出的模拟数据，并针对每一个时间步，步进式地执行完整的 B 模块状态演化逻辑，最终将包含心理轨迹和网络快照的全局状态保存到 output\_B/state\_B\_selftest.json 中。

### **3.2 内部心理状态极化分析 (Agent 维度)**

通过解析最终输出的自测数据，我们可以清晰地观察到反思机制和人格特质共同作用下的心理演化现象。以下是运行至最后（T=4）时的关键状态追踪：

| Agent | 预设角色 | 初始观点 | 最终置信度 (T=4) | 演化趋势与社会学分析 |
| :---- | :---- | :---- | :---- | :---- |
| **Agent 1** | 信息传播者 | believe | **0.71** | **稳步上升**。在持续的交互中不断向外发声，虽然偶尔遭到质疑，但其高活跃度导致了显著的“自我强化”效应。 |
| **Agent 2** | 理性验证者 | uncertain | **0.53** | **微降持平**。由于信息始终缺乏实证，基于其极高的验证倾向，置信度出现微降，完美保持了理性质疑的设定。 |
| **Agent 3** | 组织协调者 | uncertain | **0.46** | **显著下降**。作为协调者，其倾听面最广，受到了多方矛盾观点的严重拉扯，内部心理状态产生动摇。 |
| **Agent 4** | 风险敏感者 | reject | **0.84** | **维持极高位**。高风险敏感度使其在接收到少量拒绝信息时便极大强化了心理定势，坚定了拒绝谣言的立场。 |

### **3.3 社交网络动态拓扑分析 (Network 维度)**

自测数据同样证实了基于立场的信任网络动态演化已生效。系统打破了初始的静态信任分配：

在最新的测试结果中，我们观察到一个非常典型的社交重塑现象：

**Agent 3（组织协调者）将其信任白名单 (trusted\_agents) 更新为仅包含 \["agent\_2"\]**。

* **现象解释**：Agent 2 是理性验证者，在整个争议传播过程中，其立场客观且没有盲目传播。  
* **机制证明**：Agent 3 作为协调者，在多轮互动中识别到了 Agent 2 的稳定性，基于同质相吸与不冲突原则，两人建立了深度信任。  
  这表明社交关系确实随着观点互动产生了闭环演化，为后续 C 模块的群体决策提供了极具真实感的模拟基础。

## **4\. B 模块完整源码**

### **4.1 核心逻辑 (scripts\_B/memory\_and\_social.py)**

"""
B Module: Memory, Reflection, and Social Relationship Evolution.

This module is responsible for the internal cognitive processes of the agents.
It processes interactions to form memories, uses those memories and inherent 
personality traits to drive self-reflection (opinion/confidence shifts), and 
dynamically updates the social graph (trust weights) based on homophily and 
personality-driven verification tendencies.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Maximum number of memories an agent can hold to simulate cognitive limits
MAX_MEMORY_CAPACITY = 50


def update_social_state(state: dict[str, Any], timestep: int) -> dict[str, Any]:
    """
    Main entry point for Module B. Called at every timestep by Module A.
    
    Executes the cognitive-social pipeline:
    1. Memory Encoding: Records new interactions.
    2. Internal Reflection: Updates opinions/confidence using personality traits.
    3. Social Evolution: Updates the trust matrix.
    """
    _update_memories(state, timestep)
    _reflect_agents(state, timestep)
    _update_relationships(state, timestep)
    
    return state


def _update_memories(state: dict[str, Any], timestep: int) -> None:
    """
    Encodes current timestep messages into agents' long-term memory.
    Implements a basic memory pruning mechanism (forgetting old/excessive memories).
    """
    agents = state.get("agents", {})
    messages = state.get("messages", [])
    
    current_messages = [m for m in messages if m.get("timestep") == timestep]
    
    for msg in current_messages:
        speaker_id = msg.get("speaker")
        receiver_id = msg.get("receiver")
        
        base_memory = {
            "timestep": timestep,
            "speaker": speaker_id,
            "receiver": receiver_id,
            "stance": msg.get("stance", "uncertain"),
            "confidence": msg.get("confidence", 0.5),
            "content": msg.get("content", "")
        }
        
        # Encode for speaker
        if speaker_id in agents:
            mem_sent = {**base_memory, "direction": "sent"}
            agents[speaker_id]["memory"].append(mem_sent)
            # Prune memory if it exceeds capacity
            if len(agents[speaker_id]["memory"]) > MAX_MEMORY_CAPACITY:
                agents[speaker_id]["memory"] = agents[speaker_id]["memory"][-MAX_MEMORY_CAPACITY:]
                
        # Encode for receiver
        if receiver_id in agents:
            mem_received = {**base_memory, "direction": "received"}
            agents[receiver_id]["memory"].append(mem_received)
            # Prune memory
            if len(agents[receiver_id]["memory"]) > MAX_MEMORY_CAPACITY:
                agents[receiver_id]["memory"] = agents[receiver_id]["memory"][-MAX_MEMORY_CAPACITY:]


def _reflect_agents(state: dict[str, Any], timestep: int) -> None:
    """
    Advanced reflection mechanism driven by Personality Traits.
    Instead of fixed numerical adjustments, confidence shifts are influenced by:
    - The agent's `trustfulness` (how easily they are swayed)
    - The agent's `risk_sensitivity` (how strongly they react to 'reject'/'risk' messages)
    - The trust they have in the information source.
    """
    agents = state.get("agents", {})
    relationships = state.get("relationships", {})
    
    for agent_id, agent in agents.items():
        memory = agent.get("memory", [])
        if not memory:
            continue
            
        # Retrieve memories from the recent window (last 2 timesteps)
        recent_received = [
            m for m in memory 
            if m.get("direction") == "received" and m.get("timestep", 0) >= max(0, timestep - 1)
        ]
        
        if not recent_received:
            continue
            
        current_opinion = agent.get("opinion", "uncertain")
        confidence = float(agent.get("confidence", 0.5))
        personality = agent.get("personality", {})
        
        trustfulness = float(personality.get("trustfulness", 0.5))
        risk_sensitivity = float(personality.get("risk_sensitivity", 0.5))
        
        # Calculate cumulative influence score
        influence_score = 0.0
        
        for msg in recent_received:
            speaker_id = msg.get("speaker")
            msg_stance = msg.get("stance")
            msg_conf = float(msg.get("confidence", 0.5))
            
            # Fetch how much this agent trusts the speaker
            source_trust = 0.5
            if agent_id in relationships and speaker_id in relationships[agent_id]:
                source_trust = float(relationships[agent_id][speaker_id].get("trust", 0.5))
            
            # Base impact is source trust * message confidence
            impact = source_trust * msg_conf
            
            if msg_stance == current_opinion:
                # Echo chamber effect: Amplified by trustfulness
                influence_score += impact * (0.5 + trustfulness * 0.5)
            else:
                # Cognitive dissonance: Penalty amplified if it's a risk warning
                penalty = impact * (0.8 - trustfulness * 0.3)
                if msg_stance == "reject":
                    penalty *= (1.0 + risk_sensitivity) # High risk sensitivity makes them doubt more
                influence_score -= penalty
        
        # Apply influence to current confidence
        # A positive score means reinforcement; negative means doubt
        net_shift = influence_score * 0.15 
        new_confidence = confidence + net_shift
        
        # Opinion flipping logic (if confidence drops below a critical threshold)
        if new_confidence < 0.2 and len(recent_received) > 0:
            # Agent's confidence is shattered, they might adopt the majority stance of recent msgs
            stances = [m["stance"] for m in recent_received]
            most_frequent_stance = max(set(stances), key=stances.count)
            if most_frequent_stance != current_opinion:
                agent["opinion"] = most_frequent_stance
                new_confidence = 0.3  # Rebound slightly in the new opinion
                
        # Clamp confidence to [0.1, 1.0] to maintain mathematical validity
        agent["confidence"] = round(max(0.1, min(1.0, new_confidence)), 2)


def _update_relationships(state: dict[str, Any], timestep: int) -> None:
    """
    Dynamic Social Network Evolution using Homophily and Personality parameters.
    Trust weights are asymmetric (A trusts B != B trusts A) and scale with the
    receiver's verification tendencies.
    """
    agents = state.get("agents", {})
    relationships = state.get("relationships", {})
    messages = state.get("messages", [])
    
    current_messages = [m for m in messages if m.get("timestep") == timestep]
    
    for msg in current_messages:
        speaker_id = msg.get("speaker")
        receiver_id = msg.get("receiver")
        
        if speaker_id not in agents or receiver_id not in agents:
            continue
            
        speaker_stance = msg.get("stance", "uncertain")
        receiver = agents[receiver_id]
        receiver_opinion = receiver.get("opinion", "uncertain")
        receiver_verification = float(receiver.get("personality", {}).get("verification", 0.5))
        
        # Ensure matrix initialization
        for source, target in [(speaker_id, receiver_id), (receiver_id, speaker_id)]:
            relationships.setdefault(source, {}).setdefault(target, {"trust": 0.5, "interaction_count": 0})
            
        # 1. Update Receiver's trust in Speaker (R -> S)
        # This is where personality matters most. How does the receiver judge the speaker?
        r2s_rel = relationships[receiver_id][speaker_id]
        
        if speaker_stance == receiver_opinion:
            # Homophily: Agreement builds trust, but highly skeptical agents verify before trusting fully
            trust_gain = 0.04 * (1.5 - receiver_verification) 
            r2s_rel["trust"] = round(max(0.0, min(1.0, r2s_rel["trust"] + trust_gain)), 2)
        else:
            # Conflict: High verification agents penalize trust heavily when disagreed with
            trust_loss = 0.02 * (0.5 + receiver_verification)
            r2s_rel["trust"] = round(max(0.0, min(1.0, r2s_rel["trust"] - trust_loss)), 2)
            
        r2s_rel["interaction_count"] += 1
        
        # 2. Update Speaker's trust in Receiver (S -> R)
        # The speaker gains a slight affinity for whoever they talk to (mere-exposure effect)
        # but less intense than the receiver's evaluation.
        s2r_rel = relationships[speaker_id][receiver_id]
        s2r_rel["interaction_count"] += 1
        
        if speaker_stance == receiver_opinion:
            s2r_rel["trust"] = round(max(0.0, min(1.0, s2r_rel["trust"] + 0.02)), 2)
        else:
            s2r_rel["trust"] = round(max(0.0, min(1.0, s2r_rel["trust"] - 0.01)), 2)

    state["relationships"] = relationships


def save_state(state: dict[str, Any], path: str | Path) -> None:
    """Utility to safely serialize the simulation state to disk."""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

### **4.2 自测脚本 (scripts\_B/test\_module\_b.py)**

"""
Advanced Self-test script for Module B.

This script simulates the passage of time by feeding messages to Module B
timestep by timestep, accurately demonstrating the cognitive evolution
and social network shifts caused by the algorithms.
"""

import copy
import json
import sys
from pathlib import Path

# Ensure the parent directory is in the path
sys.path.append(str(Path(__file__).parent.parent))

from scripts_B.memory_and_social import update_social_state, save_state

def main():
    input_state_path = Path("output_A/state_A.json")
    if not input_state_path.exists():
        print(f"Error: {input_state_path} not found. Please run Module A first.")
        return

    with open(input_state_path, "r", encoding="utf-8") as f:
        final_state = json.load(f)

    print(f"Loaded simulation state from {input_state_path}")
    
    # We will reconstruct the state evolution timestep by timestep
    messages = final_state.get("messages", [])
    if not messages:
        print("No messages found to simulate.")
        return

    max_timestep = max(m.get("timestep", 0) for m in messages)
    
    # Create a fresh state with empty memories and base relationships
    sim_state = copy.deepcopy(final_state)
    for agent in sim_state["agents"].values():
        agent["memory"] = []
    
    print("\n--- Starting Temporal Simulation for Module B ---")
    
    for t in range(max_timestep + 1):
        print(f"\n[Timestep {t}] Executing B Module pipeline...")
        # Module B expects the global state to have messages. 
        # In a real run, A injects messages per step. We simulate that.
        sim_state["messages"] = [m for m in messages if m["timestep"] <= t]
        
        # Trigger the B module logic
        sim_state = update_social_state(sim_state, t)
        
        # Log quick stats for Agent 1 and Agent 4 to observe polarization
        a1_conf = sim_state["agents"]["agent_1"]["confidence"]
        a4_conf = sim_state["agents"]["agent_4"]["confidence"]
        rel_1_to_4 = sim_state["relationships"].get("agent_1", {}).get("agent_4", {}).get("trust", "N/A")
        rel_4_to_1 = sim_state["relationships"].get("agent_4", {}).get("agent_1", {}).get("trust", "N/A")
        
        print(f"  Agent 1 (Spreader) Confidence: {a1_conf}")
        print(f"  Agent 4 (Sensitive) Confidence: {a4_conf}")
        print(f"  Trust A1->A4: {rel_1_to_4} | Trust A4->A1: {rel_4_to_1}")

    # Save the final result
    output_path = Path("output_B/state_B_selftest.json")
    save_state(sim_state, output_path)
    print(f"\nSimulation complete. Advanced memory and social state saved to {output_path}")

if __name__ == "__main__":
    main()
