"""Persist agent runs and estimate time saved vs. manual work.

Each agent run records which tools were invoked and how long it took. Every tool
maps to an estimated number of minutes a human would need to do the same task
by hand, so the frontend can show "time saved" at the top of the page.

Records are stored in a JSON file so totals survive service restarts.
"""

import json
import os
import threading
import time
from pathlib import Path

# Estimated minutes a human would take to complete each task manually.
MANUAL_BASELINE_MINUTES: dict[str, float] = {
    "login_to_carematch": 1.0,
    "list_trials": 2.0,
    "get_trial": 2.0,
    "create_trial": 15.0,
    "update_trial": 5.0,
    "evaluate_eligibility": 20.0,
    "list_assessments": 2.0,
    "get_assessment": 2.0,
    "approve_assessment": 5.0,
    "override_rule": 10.0,
    "list_caregivers_for_patient": 2.0,
    "create_caregiver": 5.0,
    "list_audit_logs": 2.0,
    "get_metrics": 1.0,
}

# These actions just inspect data; they do not count toward "time saved".
OBSERVATION_TOOLS = {
    "list_trials",
    "get_trial",
    "list_assessments",
    "get_assessment",
    "list_caregivers_for_patient",
    "list_audit_logs",
    "get_metrics",
}


class AgentMetricsStore:
    def __init__(self, path: str = "agent_metrics.json"):
        self._path = Path(path)
        self._lock = threading.Lock()
        self._records: list[dict] = self._load()

    def _load(self) -> list[dict]:
        if not self._path.exists():
            return []
        try:
            data = json.loads(self._path.read_text())
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, OSError):
            return []

    def record_run(self, actions: list[str], duration_s: float) -> dict:
        counts: dict[str, int] = {}
        for name in actions:
            counts[name] = counts.get(name, 0) + 1

        manual_minutes = sum(
            MANUAL_BASELINE_MINUTES.get(name, 0.0) * count for name, count in counts.items()
        )
        saved_minutes = max(0.0, manual_minutes - duration_s / 60.0)

        record = {
            "ts": time.time(),
            "actions": counts,
            "duration_s": round(duration_s, 2),
            "manual_minutes": round(manual_minutes, 2),
            "saved_minutes": round(saved_minutes, 2),
        }
        with self._lock:
            self._records.append(record)
            self._save()
        return record

    def _save(self) -> None:
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._records, indent=2))
        os.replace(tmp, self._path)

    def summary(self) -> dict:
        with self._lock:
            runs = len(self._records)
            total_saved = round(sum(r["saved_minutes"] for r in self._records), 2)
            total_manual = round(sum(r["manual_minutes"] for r in self._records), 2)
            action_counts: dict[str, int] = {}
            for r in self._records:
                for name, count in r["actions"].items():
                    action_counts[name] = action_counts.get(name, 0) + count
            return {
                "runs": runs,
                "saved_minutes": total_saved,
                "manual_minutes": total_manual,
                "actions": action_counts,
            }
