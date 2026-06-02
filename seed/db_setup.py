"""
Creates the minimal test database schema required by the seed scripts.

Run this once against the test database before executing any seed script.
The statements use CREATE TABLE IF NOT EXISTS, so re-running is safe.

Usage:
    python -m seed.db_setup
"""

import sys
from seed.db import get_connection

DDL = """
CREATE TABLE IF NOT EXISTS inventory_item (
    id               SERIAL PRIMARY KEY,
    display_name     VARCHAR(255) UNIQUE NOT NULL,
    category         VARCHAR(100),
    base_uom         VARCHAR(50),
    reorder_threshold INTEGER,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS item_property (
    id             SERIAL PRIMARY KEY,
    item_id        INTEGER NOT NULL REFERENCES inventory_item(id) ON DELETE CASCADE,
    property_name  VARCHAR(100) NOT NULL,
    property_value NUMERIC(12, 4),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (item_id, property_name)
);

CREATE TABLE IF NOT EXISTS batch_field (
    id          SERIAL PRIMARY KEY,
    item_id     INTEGER NOT NULL REFERENCES inventory_item(id) ON DELETE CASCADE,
    field_name  VARCHAR(255) NOT NULL,
    field_key   VARCHAR(100) NOT NULL,
    field_type  VARCHAR(50)  DEFAULT 'text',
    is_required BOOLEAN      DEFAULT FALSE,
    created_at  TIMESTAMPTZ  DEFAULT NOW(),
    UNIQUE (item_id, field_key)
);
"""


def main():
    print("Connecting to database ...")
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
        print("Schema created/verified successfully.")
        print("  Tables: inventory_item, item_property, batch_field")
    except Exception as exc:
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
