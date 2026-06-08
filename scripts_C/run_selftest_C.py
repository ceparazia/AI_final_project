"""Self-test C module with A module outputs.

Run from the repository root:

    python scripts_C\run_selftest_C.py

The script does not run a full experiment. It only validates C's debate and
metrics logic on A's mock/fallback states, then writes output_C artifacts.
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

