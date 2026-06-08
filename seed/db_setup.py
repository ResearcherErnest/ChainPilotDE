"""
Verifies the target database schema used by all de_2_x seed scripts.

The schema is managed by the backend's Flyway migrations and is already
present in the test database. This script checks that the required tables
exist and reports their current row counts — it does NOT recreate tables.

Run before any seed script to confirm the DB is ready:
    python -m seed.db_setup

Expected tables:
    unit_of_measure       — UOM catalogue  (seeded by de_2_1)
    category              — item categories (seeded by de_2_1)
    inventory_item        — material catalogue; specs in attributes JSONB
    batch_field_definition — per-item intake form field definitions
    item_grade            — optional quality grades per item
    warehouse_location    — physical storage locations
"""

import sys
from seed.db import get_connection

REQUIRED_TABLES = [
    "unit_of_measure",
    "category",
    "inventory_item",
    "batch_field_definition",
    "item_grade",
    "warehouse_location",
]


def main():
    print("Checking database schema ...\n")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            missing = []
            for tbl in REQUIRED_TABLES:
                cur.execute(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = %s",
                    (tbl,),
                )
                exists = cur.fetchone()[0] == 1
                if exists:
                    cur.execute(f"SELECT COUNT(*) FROM {tbl}")
                    rows = cur.fetchone()[0]
                    print(f"  OK  {tbl:<30} {rows} rows")
                else:
                    print(f"  MISSING  {tbl}")
                    missing.append(tbl)

        if missing:
            print(f"\nERROR: {len(missing)} required table(s) missing: {missing}")
            print("Ensure the backend Flyway migrations have run against this database.")
            sys.exit(1)
        else:
            print("\nAll required tables present.")
            print("\nNext steps:")
            print("  1. python -m seed.de_2_1_seed_reference_data  (seed UOMs + categories)")
            print("  2. python -m seed.de_2_2_seed_inventory_items (seed items from Excel)")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
