"""
DE-2.1: Seed reference data — unit_of_measure and category tables.

Inserts the same rows that the backend's ReferenceDataSeeder (Java) writes
on startup. Running this script against the test DB makes the schema ready
for de_2_2 without needing the backend to be running.

Idempotency: uses ON CONFLICT (code) DO NOTHING — safe to re-run at any time.

Usage:
    python -m seed.de_2_1_seed_reference_data
"""

import sys

from seed.db import get_connection
from seed.schema_registry import CATEGORIES, UNITS_OF_MEASURE
from seed.seed_logger import SeedLogger

SCRIPT_NAME = "de_2_1"


# ── Database helpers ──────────────────────────────────────────────────────

def seed_uoms(conn, logger: SeedLogger) -> tuple:
    inserted = skipped = 0
    with conn.cursor() as cur:
        for uom in UNITS_OF_MEASURE:
            cur.execute(
                "INSERT INTO unit_of_measure (code, label) VALUES (%s, %s) ON CONFLICT (code) DO NOTHING",
                (uom["code"], uom["label"]),
            )
            if cur.rowcount:
                print(f"  INSERT UOM  {uom['code']:<8}  {uom['label']}")
                logger.log_event("INSERT", f"unit_of_measure:{uom['code']}", uom["label"])
                inserted += 1
            else:
                print(f"  SKIP   UOM  {uom['code']:<8}  (already exists)")
                logger.log_event("SKIP", f"unit_of_measure:{uom['code']}", "already exists")
                skipped += 1
    conn.commit()
    return inserted, skipped


def seed_categories(conn, logger: SeedLogger) -> tuple:
    inserted = skipped = 0
    with conn.cursor() as cur:
        for cat in CATEGORIES:
            cur.execute(
                "INSERT INTO category (code, name, description) VALUES (%s, %s, %s) ON CONFLICT (code) DO NOTHING",
                (cat["code"], cat["name"], cat.get("description")),
            )
            if cur.rowcount:
                print(f"  INSERT CAT  {cat['code']:<16}  {cat['name']}")
                logger.log_event("INSERT", f"category:{cat['code']}", cat["name"])
                inserted += 1
            else:
                print(f"  SKIP   CAT  {cat['code']:<16}  (already exists)")
                logger.log_event("SKIP", f"category:{cat['code']}", "already exists")
                skipped += 1
    conn.commit()
    return inserted, skipped


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    print("DE-2.1: Seed reference data\n")
    logger = SeedLogger(SCRIPT_NAME)
    logger.log_run_start(
        description="Seed unit_of_measure and category reference data",
        mode="full",
    )
    conn = get_connection()
    try:
        print("Units of measure:")
        uom_ins, uom_skip = seed_uoms(conn, logger)

        print("\nCategories:")
        cat_ins, cat_skip = seed_categories(conn, logger)

    except Exception as exc:
        conn.rollback()
        logger.log_event("FAIL", "de_2_1:setup", str(exc))
        logger.log_run_end("error", str(exc))
        print(f"\nERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()

    summary = (f"UOMs: inserted={uom_ins} skipped={uom_skip}  "
               f"Categories: inserted={cat_ins} skipped={cat_skip}")
    logger.log_run_end("ok", summary)

    print("\n" + "=" * 52)
    print("DE-2.1 SUMMARY")
    print(f"  UOMs       : inserted={uom_ins}  skipped={uom_skip}")
    print(f"  Categories : inserted={cat_ins}  skipped={cat_skip}")
    print("=" * 52)
    print("\nNext: python -m seed.de_2_2_seed_inventory_items")


if __name__ == "__main__":
    main()
