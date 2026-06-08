"""
Manages seed_failures.log and seed_audit.log for all seed scripts.

seed_failures.log  — JSON lines; one object per failed operation.
                     Consumed (entries removed) on successful retry.
seed_audit.log     — JSON lines; append-only audit trail.

Each failure entry:
    {
        "script":    "de_1_1",
        "key":       "6MM",          # tab name / header / material name
        "reason":    "...",
        "detail":    "...",          # raw value / row number / full context
        "timestamp": "2025-01-01T00:00:00"
    }

Each audit entry:
    {
        "script":    "de_1_4",
        "material":  "9mm MDF",
        "field":     "reorder_threshold",
        "old_value": null,
        "new_value": 500,
        "action":    "update",
        "timestamp": "2025-01-01T00:00:00"
    }
"""

import json
import os
from datetime import datetime, timezone

from config import LOGS_DIR

FAILURES_LOG = str(LOGS_DIR / "seed_failures.log")
AUDIT_LOG    = str(LOGS_DIR / "seed_audit.log")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_failures() -> list:
    if not os.path.exists(FAILURES_LOG):
        return []
    entries = []
    with open(FAILURES_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def _write_failures(entries: list) -> None:
    os.makedirs(LOGS_DIR, exist_ok=True)
    with open(FAILURES_LOG, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


class SeedLogger:
    def __init__(self, script: str):
        self.script = script
        os.makedirs(LOGS_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Failure log                                                          #
    # ------------------------------------------------------------------ #

    def log_failure(self, key: str, reason: str, detail: str = "") -> None:
        """Upsert a failure entry for (script, key) in seed_failures.log."""
        entries = _read_failures()
        # Remove any previous entry for this key+script so we get a fresh timestamp.
        entries = [e for e in entries if not (e.get("script") == self.script and e.get("key") == key)]
        entries.append({
            "script": self.script,
            "key": key,
            "reason": reason,
            "detail": detail,
            "timestamp": _now(),
        })
        _write_failures(entries)

    def log_success(self, key: str) -> None:
        """Remove the failure entry for (script, key) from seed_failures.log."""
        entries = _read_failures()
        entries = [e for e in entries if not (e.get("script") == self.script and e.get("key") == key)]
        _write_failures(entries)

    def get_failures(self, script: str | None = None) -> list:
        """Return all failure entries for the given script (default: self.script)."""
        target = script if script is not None else self.script
        return [e for e in _read_failures() if e.get("script") == target]

    def get_failed_keys(self, script: str | None = None) -> set:
        """Return the set of failed keys for the given script."""
        return {e["key"] for e in self.get_failures(script)}

    # ------------------------------------------------------------------ #
    # Audit log (append-only)                                             #
    # ------------------------------------------------------------------ #

    def log_run_start(self, description: str, mode: str = "full") -> None:
        """Write a RUN_START header to seed_audit.log at the top of every script run."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        entry = {
            "type":        "RUN_START",
            "ts":          _now(),
            "script":      self.script,
            "description": description,
            "mode":        mode,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_run_end(self, result: str, summary: str = "") -> None:
        """Write a RUN_END footer to seed_audit.log after every script run."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        entry = {
            "type":    "RUN_END",
            "ts":      _now(),
            "script":  self.script,
            "result":  result,
            "summary": summary,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_event(self, action: str, entity: str, detail: str = "") -> None:
        """
        Append one structured event to seed_audit.log.

        Fields:
            ts      — ISO-8601 UTC timestamp
            script  — script name (e.g. 'de_2_2')
            action  — INSERT | SKIP | CREATE | FAIL | UPDATE
            entity  — '<table>:<key>'  e.g. 'inventory_item:RM-MDF-9MM'
            detail  — human-readable context (name, row count, error text)
        """
        os.makedirs(LOGS_DIR, exist_ok=True)
        entry = {
            "ts":     _now(),
            "script": self.script,
            "action": action,
            "entity": entity,
            "detail": detail,
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def log_audit(
        self,
        material: str,
        old_value,
        new_value,
        action: str,
        field: str = "reorder_threshold",
    ) -> None:
        """Legacy audit method used by de_1_4. Kept for backward compatibility."""
        os.makedirs(LOGS_DIR, exist_ok=True)
        entry = {
            "script": self.script,
            "material": material,
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "action": action,
            "timestamp": _now(),
        }
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
