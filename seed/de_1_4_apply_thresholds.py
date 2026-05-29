"""
DE-1.4: Apply reorder thresholds from thresholds.json.

Reads seed/thresholds.json and issues one UPDATE per listed material.
Materials not in the config are left with their existing (or null) threshold.
Each change is recorded in seed_audit.log with before/after values.

Config validation:
  - If thresholds.json is missing → exit immediately, no DB changes.
  - If JSON is malformed or missing required keys → exit immediately, no DB changes.
  - Each threshold value must be a positive integer.

Idempotency:
  - If the material already has the correct threshold → skip (logged in audit as 'skip').
  - If the material now exists after a previous blocked run → apply correctly on retry.

Usage:
    python -m seed.de_1_4_apply_thresholds
    python -m seed.de_1_4_apply_thresholds --retry
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from seed.db import get_connection
from seed.seed_logger import SeedLogger

SCRIPT_NAME = "de_1_4"
THRESHOLDS_FILE = os.path.join(os.path.dirname(__file__), "thresholds.json")


# ------------------------------------------------------------------ #
# Config loading and validation                                        #
# ------------------------------------------------------------------ #

def load_and_validate_config() -> dict:
    """
    Load thresholds.json and return the thresholds dict.
    Exits immediately on any validation failure — no DB state is touched.
    """
    if not os.path.exists(THRESHOLDS_FILE):
        print(
            f"ERROR: Config file not found: {THRESHOLDS_FILE}\n"
            "Create seed/thresholds.json before running this script.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        with open(THRESHOLDS_FILE, encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: thresholds.json is not valid JSON: {exc}\n"
            "Fix the file and re-run. No database changes were made.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not isinstance(raw, dict):
        print("ERROR: thresholds.json must be a JSON object at the top level.", file=sys.stderr)
        sys.exit(1)

    if "thresholds" not in raw:
        print(
            "ERROR: thresholds.json is missing required key 'thresholds'.\n"
            "Expected structure: {\"thresholds\": {\"9mm MDF\": 500, ...}}",
            file=sys.stderr,
        )
        sys.exit(1)

    thresholds = raw["thresholds"]
    if not isinstance(thresholds, dict):
        print("ERROR: 'thresholds' must be a JSON object mapping display_name → integer.", file=sys.stderr)
        sys.exit(1)

    # Validate all values are positive integers
    errors = []
    for name, value in thresholds.items():
        if not isinstance(value, int) or value <= 0:
            errors.append(f"  '{name}': {value!r} (must be a positive integer)")
    if errors:
        print("ERROR: Invalid threshold values in thresholds.json:\n" + "\n".join(errors), file=sys.stderr)
        print("No database changes were made.", file=sys.stderr)
        sys.exit(1)

    return thresholds


# ------------------------------------------------------------------ #
# Database helpers                                                     #
# ------------------------------------------------------------------ #

def db_get_material(conn, display_name: str):
    """Return (item_id, current_threshold) or (None, None) if not found."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, reorder_threshold FROM inventory_item WHERE display_name = %s",
            (display_name,),
        )
        row = cur.fetchone()
    if row is None:
        return None, None
    return row[0], row[1]


def db_update_threshold(conn, item_id: int, threshold: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE inventory_item SET reorder_threshold = %s, updated_at = NOW() WHERE id = %s",
            (threshold, item_id),
        )
    conn.commit()


# ------------------------------------------------------------------ #
# Entry point                                                          #
# ------------------------------------------------------------------ #

def main():
    parser = argparse.ArgumentParser(description="DE-1.4: Apply reorder thresholds from thresholds.json")
    parser.add_argument("--retry", action="store_true")
    args = parser.parse_args()

    # Validate config BEFORE opening any DB connection
    print(f"Loading config: {THRESHOLDS_FILE}")
    thresholds = load_and_validate_config()
    print(f"  {len(thresholds)} material(s) configured: {', '.join(sorted(thresholds))}\n")

    logger = SeedLogger(SCRIPT_NAME)
    failed_keys = logger.get_failed_keys()
    is_retry = args.retry or bool(failed_keys)

    if is_retry:
        print(f"RETRY mode — {len(failed_keys)} key(s) pending: {sorted(failed_keys)}\n")
    else:
        print("FULL mode — processing all configured materials\n")

    conn = get_connection()

    succeeded = skipped = blocked = failed = 0

    for display_name, new_threshold in thresholds.items():
        retry_key = display_name

        if is_retry and retry_key not in failed_keys:
            print(f"  SKIP  [{display_name}] — not in retry list (previously applied)")
            skipped += 1
            continue

        item_id, current_threshold = db_get_material(conn, display_name)

        if item_id is None:
            msg = f"Material '{display_name}' not found in DB — blocked on DE-1.1"
            logger.log_failure(retry_key, msg, f"display_name='{display_name}'")
            logger.log_audit(display_name, None, new_threshold, "blocked")
            print(f"  BLOCK [{display_name}] — not in DB; run DE-1.1 first")
            blocked += 1
            continue

        if current_threshold == new_threshold:
            logger.log_success(retry_key)
            logger.log_audit(display_name, current_threshold, new_threshold, "skip")
            print(f"  SKIP  [{display_name}] — threshold already {new_threshold}")
            skipped += 1
            continue

        try:
            db_update_threshold(conn, item_id, new_threshold)
            logger.log_success(retry_key)
            logger.log_audit(display_name, current_threshold, new_threshold, "update")
            print(
                f"  UPDATE[{display_name}] "
                f"{current_threshold!r} → {new_threshold}"
            )
            succeeded += 1
        except Exception as exc:
            conn.rollback()
            logger.log_failure(retry_key, f"DB update error: {exc}", f"item_id={item_id}")
            logger.log_audit(display_name, current_threshold, new_threshold, "error")
            print(f"  FAIL  [{display_name}] {exc}")
            failed += 1

    conn.close()

    print("\n" + "=" * 52)
    print("DE-1.4 SUMMARY")
    print(f"  Updated : {succeeded}")
    print(f"  Skipped : {skipped}  (already correct)")
    print(f"  Blocked : {blocked}  (material not yet in DB)")
    print(f"  Failed  : {failed}")
    from seed.seed_logger import AUDIT_LOG
    print(f"  Audit log: {AUDIT_LOG}")
    if failed or blocked:
        from seed.seed_logger import FAILURES_LOG
        print(f"  Failure log: {FAILURES_LOG}")
    print("=" * 52)

    sys.exit(1 if (failed or blocked) else 0)


if __name__ == "__main__":
    main()
