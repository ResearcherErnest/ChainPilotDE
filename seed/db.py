"""
Shared database connection helper for all seed scripts.
Reads DATABASE_URL from config (which loads it from .env).
"""

import sys

import psycopg2

from config import DATABASE_URL


def get_connection() -> psycopg2.extensions.connection:
    """Return an open psycopg2 connection using DATABASE_URL from config."""
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL is not set. Copy .env.example → .env and configure it.", file=sys.stderr)
        sys.exit(1)
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Cannot connect to database: {exc}", file=sys.stderr)
        sys.exit(1)
