"""
Audit log viewer — renders seed_audit.log as readable, navigable output.

Usage:
    python -m seed.audit_viewer               # all runs
    python -m seed.audit_viewer --script de_2_2   # filter by script
    python -m seed.audit_viewer --fails           # only runs/events with failures
    python -m seed.audit_viewer --last 3          # last N runs only
    python -m seed.audit_viewer --summary         # run headers + results only
"""

import argparse
import json
import os
import sys

from config import LOGS_DIR

AUDIT_LOG = str(LOGS_DIR / "seed_audit.log")

W = 72  # line width

ACTION_LABEL = {
    "INSERT": "INSERT",
    "CREATE": "CREATE",
    "UPDATE": "UPDATE",
    "SKIP":   "SKIP  ",
    "FAIL":   "FAIL  ",
}

RESULT_LABEL = {
    "ok":    "OK   ",
    "error": "ERROR",
}


# ── Log reader ────────────────────────────────────────────────────────────

def load_entries() -> list:
    if not os.path.exists(AUDIT_LOG):
        return []
    entries = []
    with open(AUDIT_LOG, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def group_into_runs(entries: list) -> list:
    """
    Group log entries into run blocks.
    Each block: {"start": {...}, "events": [...], "end": {...} | None}
    Orphan events (no RUN_START) go into a synthetic block.
    """
    runs = []
    current = None

    for e in entries:
        etype = e.get("type")
        if etype == "RUN_START":
            current = {"start": e, "events": [], "end": None}
            runs.append(current)
        elif etype == "RUN_END":
            if current:
                current["end"] = e
            else:
                runs.append({"start": None, "events": [], "end": e})
            current = None
        else:
            if current is None:
                current = {"start": None, "events": [], "end": None}
                runs.append(current)
            current["events"].append(e)

    return runs


# ── Rendering helpers ─────────────────────────────────────────────────────

def fmt_ts(ts: str) -> str:
    """'2026-06-05T14:32:42Z' -> '2026-06-05  14:32:42'"""
    return ts.replace("T", "  ").rstrip("Z") if ts else ""


def has_failure(run: dict) -> bool:
    if run.get("end", {}) and run["end"].get("result") == "error":
        return True
    return any(e.get("action") == "FAIL" for e in run["events"])


def render_run(run: dict, idx: int, summary_only: bool) -> list:
    lines = []
    start = run.get("start") or {}
    end   = run.get("end")   or {}

    script = start.get("script") or end.get("script") or "unknown"
    ts     = fmt_ts(start.get("ts") or end.get("ts") or "")
    mode   = start.get("mode", "")
    desc   = start.get("description", "")

    result  = end.get("result", "")
    summary = end.get("summary", "")

    result_tag = RESULT_LABEL.get(result, result.upper() if result else "")

    # ── Header ───────────────────────────────────────────────────────────
    lines.append("=" * W)
    header = f"  RUN #{idx}  |  {script}  |  {ts}  |  {mode}"
    lines.append(header)
    if desc:
        lines.append(f"  {desc}")
    lines.append("=" * W)

    if not summary_only:
        # ── Events ───────────────────────────────────────────────────────
        for e in run["events"]:
            action = ACTION_LABEL.get(e.get("action", ""), e.get("action", "")[:6].ljust(6))
            entity = e.get("entity", "")
            detail = e.get("detail", "")
            entity_col = f"{entity:<40}"
            lines.append(f"  {action}  {entity_col}  {detail}")

        if run["events"]:
            lines.append("-" * W)

    # ── Result footer ─────────────────────────────────────────────────────
    if result or summary:
        lines.append(f"  RESULT: {result_tag}  |  {summary}")

    lines.append("")
    return lines


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Render seed_audit.log as readable run blocks"
    )
    parser.add_argument("--script",  help="Show only runs for this script (e.g. de_2_2)")
    parser.add_argument("--fails",   action="store_true", help="Show only runs with failures")
    parser.add_argument("--last",    type=int, metavar="N", help="Show last N runs only")
    parser.add_argument("--summary", action="store_true",   help="Run headers + results only")
    args = parser.parse_args()

    entries = load_entries()
    if not entries:
        print(f"No entries in {AUDIT_LOG}")
        sys.exit(0)

    runs = group_into_runs(entries)

    # ── Filters ───────────────────────────────────────────────────────────
    if args.script:
        runs = [
            r for r in runs
            if (r.get("start") or {}).get("script") == args.script
            or (r.get("end")   or {}).get("script") == args.script
        ]
    if args.fails:
        runs = [r for r in runs if has_failure(r)]
    if args.last:
        runs = runs[-args.last:]

    if not runs:
        print("No matching runs found.")
        sys.exit(0)

    # ── Count totals ──────────────────────────────────────────────────────
    total  = len(runs)
    failed = sum(1 for r in runs if has_failure(r))

    print()
    print(f"  seed_audit.log  —  {total} run(s) shown"
          + (f"  ({failed} with failures)" if failed else ""))
    print()

    for i, run in enumerate(runs, start=1):
        for line in render_run(run, i, args.summary):
            print(line)

    print(f"  Total runs: {total}  |  Failures: {failed}"
          + ("  (use --fails to filter)" if not args.fails and failed else ""))
    print()


if __name__ == "__main__":
    main()
