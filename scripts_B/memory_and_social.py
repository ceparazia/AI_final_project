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