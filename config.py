"""
Central configuration for the ChainPilot DE pipeline.

All paths, database settings, and source file definitions live here.
Every script imports from this module — never hardcode paths or settings.

To change a setting: edit .env (copied from .env.example).
To add/remove source files: update SOURCES below.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent

# ── Directory paths ───────────────────────────────────────────────────
RAW_DATA_DIR  = ROOT / os.getenv("RAW_DATA_DIR", "Raw_data")
LOGS_DIR      = ROOT / os.getenv("LOGS_DIR", "logs")

DATA_DIR      = ROOT / "data"
STAGING_DIR   = DATA_DIR / "staging"
CATALOG_DIR   = DATA_DIR / "catalog"
PROFILES_DIR  = DATA_DIR / "profiles"
PROCESSED_DIR = DATA_DIR / "processed"
LOADED_DIR    = DATA_DIR / "loaded"

# ── File paths ────────────────────────────────────────────────────────
TRACKER_PATH = DATA_DIR / "tracker.json"
CATALOG_PATH = CATALOG_DIR / "catalog.json"
REPORT_PATH  = PROFILES_DIR / "data_quality_report.json"

# ── Database ──────────────────────────────────────────────────────────
# Set individual fields in .env — config builds the URL automatically.
# You can also set DATABASE_URL directly to override all fields.
_DB_USER     = os.getenv("DB_USER",     "chainpilot")
_DB_PASSWORD = os.getenv("DB_PASSWORD", "")
_DB_HOST     = os.getenv("DB_HOST",     "localhost")
_DB_PORT     = os.getenv("DB_PORT",     "5432")
_DB_NAME     = os.getenv("DB_NAME",     "chainpilot_test")

DATABASE_URL = (
    os.getenv("DATABASE_URL")
    or f"postgresql://{_DB_USER}:{_DB_PASSWORD}@{_DB_HOST}:{_DB_PORT}/{_DB_NAME}"
)

# ── Source file registry ──────────────────────────────────────────────
# To add a new source file, append one entry here — no script changes needed.
#
# seed_type controls which seed scripts process the file:
#   "mdf_ledger"      — multi-tab thickness workbook (de_1_1, de_1_2)
#   "glue_ledger"     — single-sheet adhesive workbook (de_1_5, de_1_6)
#   "supplier_log"    — supplier delivery workbook    (de_1_3)
#
SOURCES = [
    {
        "filename": "Stock management.xlsx",
        "source_id": "stock_management",
        "seed_type": "mdf_ledger",
        "description": "Board material stock ledger — one tab per thickness (INPUT/OUTPUT/balance)",
    },
    {
        "filename": "GLUE RECORD-1.xlsx",
        "source_id": "glue_record",
        "seed_type": "glue_ledger",
        "base_uom": "bags",
        "description": "Glue stock ledger (INPUT/OUTPUT/balance)",
    },
    {
        "filename": "Tree log suppliers Book.xlsx",
        "source_id": "tree_log_suppliers",
        "seed_type": "supplier_log",
        "description": "Supplier delivery records — summary + per-supplier tabs + received-trucks log",
    },
]
