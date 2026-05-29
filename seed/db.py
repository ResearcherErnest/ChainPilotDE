"""
Shared database connection helper for all seed scripts.
Reads DATABASE_URL from the .env file or environment.
"""

import os
import sys

import psycopg2
from dotenv import load_dotenv

load_dotenv()

_ROOT = os.path.dirname(os.path.dirname(__file__))


def get_connection() -> psycopg2.extensions.connection:
    """Return an open psycopg2 connection using DATABASE_URL."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL is not set. Copy .env.example → .env and configure it.", file=sys.stderr)
        sys.exit(1)
    try:
        return psycopg2.connect(url)
    except psycopg2.OperationalError as exc:
        print(f"ERROR: Cannot connect to database: {exc}", file=sys.stderr)
        sys.exit(1)
