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