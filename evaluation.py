"""Compatibility wrapper for A module adapter.

A's current adapter imports a top-level module named ``evaluation``. The C
module itself is stored under ``scripts_C/`` as required by README, so this
wrapper forwards the public entrypoint without changing A's code.
"""

from scripts_C.evaluation import update_debate_and_metrics

__all__ = ["update_debate_and_metrics"]

