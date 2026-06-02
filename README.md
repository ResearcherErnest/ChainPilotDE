# ChainPilot — Data Engineering

Local data engineering workspace for the ChainPilot inventory system.
Ingests client Excel datasets, profiles data quality, and seeds a
PostgreSQL test database with normalised inventory records.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Project Structure](#2-project-structure)
3. [Prerequisites](#3-prerequisites)
4. [Configuration](#4-configuration)
5. [Setup](#5-setup)
6. [Running the Pipeline](#6-running-the-pipeline)
7. [How Incremental Processing Works](#7-how-incremental-processing-works)
8. [Data Directories](#8-data-directories)
9. [Adding a New Source File](#9-adding-a-new-source-file)
10. [Idempotency and Retry](#10-idempotency-and-retry)
11. [Logs](#11-logs)
12. [Running Tests](#12-running-tests)
13. [Known Source Data Issues](#13-known-source-data-issues)

---

## 1. Architecture Overview

The pipeline has two stages that run independently:

```
Stage 1 — ETL (catalog + profile)
──────────────────────────────────────────────────────────────────
Raw_data/*.xlsx  ──►  etl/ingest_catalog.py  ──►  data/catalog/
                 └──►  etl/profile_data.py   ──►  data/profiles/
                                              └──►  data/processed/   (per-source files)

Stage 2 — Seed (load to database)
──────────────────────────────────────────────────────────────────
Raw_data/*.xlsx  ──►  seed/de_1_1  ──►  inventory_item  (materials)
                 ──►  seed/de_1_2  ──►  item_property   (MDF dimensions)
                 ──►  seed/de_1_3  ──►  batch_field     (supplier form fields)
                 ──►  seed/de_1_4  ──►  inventory_item  (reorder thresholds)
                 ──►  seed/de_1_5  ──►  inventory_item  (glue materials)
                 ──►  seed/de_1_6  ──►  item_property   (glue weight properties)
                                    └──►  data/loaded/   (load manifests per script)
```

**File tracker** (`data/tracker.json`) records the SHA-256 hash and status
of every source file so unchanged files are automatically skipped on re-runs.

```
Status lifecycle per source file:
  (new or changed content)  →  processed  →  loaded
```

---

## 2. Project Structure

```
ChainPilotDE/
│
├── config.py                          # Single config file — all paths, DB settings, sources
├── .env.example                       # Environment variable template (copy → .env)
├── .env                               # Local credentials (gitignored)
├── requirements.txt
│
├── Raw_data/                          # Immutable source Excel files — never modify
│   ├── Stock management.xlsx
│   ├── GLUE RECORD-1.xlsx
│   └── Tree log suppliers Book.xlsx
│
├── data/
│   ├── catalog/                       # catalog.json — sheet metadata for all sources
│   ├── profiles/                      # data_quality_report.json — null/type/duplicate stats
│   ├── processed/                     # Per-source catalog + profile JSON after ETL run
│   ├── loaded/                        # Per-script load manifests after successful seed run
│   ├── staging/                       # Intermediate outputs (reserved for future use)
│   └── tracker.json                   # Hash + status registry (gitignored, runtime state)
│
├── etl/
│   ├── file_tracker.py                # FileTracker — SHA-256 hash tracking, status lifecycle
│   ├── ingest_catalog.py              # DE-3: catalog all Excel sources (skips unchanged)
│   └── profile_data.py               # DE-4: profile data quality (skips unchanged)
│
├── seed/
│   ├── db.py                          # Shared DB connection helper (reads from config)
│   ├── db_setup.py                    # Create test database schema (idempotent)
│   ├── seed_logger.py                 # Failure log and audit log management
│   ├── thresholds.json                # Version-controlled reorder thresholds
│   ├── de_1_1_insert_materials.py     # DE-1.1: insert one material per MDF thickness tab
│   ├── de_1_2_parse_specs.py          # DE-1.2: parse T*W*L specs → insert dimension properties
│   ├── de_1_3_insert_batch_fields.py  # DE-1.3: read supplier headers → insert batch fields
│   ├── de_1_4_apply_thresholds.py     # DE-1.4: apply reorder thresholds from thresholds.json
│   ├── de_1_5_insert_glue.py          # DE-1.5: insert adhesive materials from glue_ledger sources
│   └── de_1_6_insert_glue_specs.py    # DE-1.6: parse glue specs → insert weight properties
│
├── docs/
│   └── source_target_mapping.md      # Source-to-target field mapping documentation
│
├── notebooks/
│   └── 01_data_exploration.ipynb     # Exploratory notebook for source Excel profiling
│
├── logs/                              # Runtime logs (gitignored except placeholder)
│   ├── seed_failures.log              # Failed operations — JSON lines, consumed on retry
│   └── seed_audit.log                # Audit trail for threshold updates — append-only
│
└── tests/
    └── test_seed_de1_1.py
```

---

## 3. Prerequisites

- Python 3.11+
- PostgreSQL 14+ running locally
- Virtual environment at `.venv/` (already initialised in this repo)

---

## 4. Configuration

All pipeline settings are controlled from **two files only**:

### `config.py` — pipeline paths, source registry, DB URL

`config.py` is the single source of truth. It reads from `.env` and exposes
every path, directory, and setting used by all scripts. **Never hardcode
paths in individual scripts** — import from `config` instead.

Key exports:

| Name | Purpose |
|------|---------|
| `ROOT` | Absolute path to project root |
| `RAW_DATA_DIR` | Source Excel files directory |
| `DATA_DIR` | All data outputs root |
| `PROCESSED_DIR` | Per-source ETL outputs |
| `LOADED_DIR` | Per-script load manifests |
| `TRACKER_PATH` | `data/tracker.json` runtime state |
| `DATABASE_URL` | Composed from `DB_*` env vars |
| `SOURCES` | List of all source file definitions |

### `.env` — credentials and path overrides

Copy `.env.example` to `.env` and fill in your values:

```env
# Database credentials — change any field independently
DB_USER=chainpilot
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
DB_NAME=chainpilot_test

# Optional: override default directory paths
# RAW_DATA_DIR=Raw_data
# LOGS_DIR=logs
```

`config.py` composes `DATABASE_URL` automatically from these fields.
You can also set `DATABASE_URL` directly to override all individual fields.

---

## 5. Setup

```powershell
# 1. Activate the virtual environment
.\.venv\Scripts\Activate.ps1          # Windows PowerShell
source .venv/bin/activate             # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure credentials
copy .env.example .env
# Edit .env — set DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME

# 4. Create the database user and database (first time only)
#    Run in psql as postgres superuser:
#    CREATE USER chainpilot WITH PASSWORD 'your_password';
#    CREATE DATABASE chainpilot_test OWNER chainpilot;
#    GRANT ALL ON SCHEMA public TO chainpilot;

# 5. Create the schema
python -m seed.db_setup
```

---

## 6. Running the Pipeline

### Stage 1 — ETL

Run catalog ingestion and data profiling before seeding. Both scripts
skip files that have not changed since the last run automatically.

```powershell
# DE-3: catalog all Excel sources → data/catalog/catalog.json
python -m etl.ingest_catalog

# DE-4: profile data quality → data/profiles/data_quality_report.json
python -m etl.profile_data

# Force reprocess all files regardless of cached status
python -m etl.ingest_catalog --force
python -m etl.profile_data --force
```

### Stage 2 — Seed (run in order)

Each script is **idempotent** — safe to re-run at any time. Run them
in the numbered order shown below; later steps depend on earlier ones.

```powershell
# DE-1.1: insert one inventory_item per MDF thickness tab
python -m seed.de_1_1_insert_materials

# DE-1.2: parse T*W*L spec strings → insert thickness/width/length properties
python -m seed.de_1_2_parse_specs

# DE-1.3: read supplier workbook header row → insert batch_field definitions
python -m seed.de_1_3_insert_batch_fields

# DE-1.4: apply reorder thresholds from seed/thresholds.json
python -m seed.de_1_4_apply_thresholds

# DE-1.5: insert glue/adhesive materials (reads all glue_ledger sources from config)
python -m seed.de_1_5_insert_glue

# DE-1.6: parse glue spec strings → insert weight_per_bag_kg and bags_per_unit
python -m seed.de_1_6_insert_glue_specs
```

On success each script writes a load manifest to `data/loaded/` and
advances the source file's status in `data/tracker.json` to `loaded`.

---

## 7. How Incremental Processing Works

The `FileTracker` class (`etl/file_tracker.py`) computes a SHA-256 hash
of each source Excel file and persists it to `data/tracker.json`.

```
On every ETL/seed run:
  1. Compute hash of source file
  2. Compare with stored hash in tracker.json
  3. If hash matches AND status is processed or loaded → SKIP
  4. If hash differs OR file is new OR status is pending → PROCESS
  5. After success → update hash + advance status
```

**Status values:**

| Status | Set by | Meaning |
|--------|--------|---------|
| `pending` | Default / after reset | File needs processing |
| `processed` | `ingest_catalog`, `profile_data` | ETL complete, ready to seed |
| `loaded` | Seed scripts (de_1_1 → de_1_6) | Data in database |

**Forcing a re-run:**

```powershell
# Re-run ETL regardless of hash
python -m etl.ingest_catalog --force

# Reset a specific file to pending via Python
python -c "
from config import RAW_DATA_DIR, TRACKER_PATH, ROOT
from etl.file_tracker import FileTracker
FileTracker(TRACKER_PATH, ROOT).reset(RAW_DATA_DIR / 'GLUE RECORD-1.xlsx')
"
```

---

## 8. Data Directories

| Directory | Contents | Written by |
|-----------|----------|-----------|
| `Raw_data/` | Source Excel files — never modified | Client |
| `data/catalog/` | `catalog.json` — combined sheet metadata | `ingest_catalog.py` |
| `data/profiles/` | `data_quality_report.json` — combined quality stats | `profile_data.py` |
| `data/processed/` | `{source_id}_catalog.json`, `{source_id}_profile.json` | ETL scripts |
| `data/loaded/` | `{source_id}_{script}.json` — load manifest per script run | Seed scripts |
| `data/tracker.json` | Hash + status per source file (gitignored) | FileTracker |
| `logs/` | `seed_failures.log`, `seed_audit.log` (gitignored) | SeedLogger |

**Load manifest example** (`data/loaded/stock_management_de_1_1.json`):

```json
{
  "script": "de_1_1",
  "source_file": "Raw_data/Stock management.xlsx",
  "mode": "full",
  "loaded_at": "2026-06-01T15:30:00+00:00",
  "summary": { "succeeded": 8, "skipped": 1, "failed": 0 }
}
```

---

## 9. Adding a New Source File

To add a new Excel source to the pipeline, add **one entry** to
`SOURCES` in `config.py`. No script changes are required.

```python
# config.py → SOURCES list
{
    "filename": "GLUE B.xlsx",
    "source_id": "glue_b",
    "seed_type": "glue_ledger",   # controls which seed scripts process this file
    "base_uom": "bags",
    "description": "Glue type B stock ledger",
},
```

**`seed_type` values:**

| Value | Processed by | When to use |
|-------|-------------|------------|
| `mdf_ledger` | DE-1.1, DE-1.2 | Multi-tab thickness workbook |
| `glue_ledger` | DE-1.5, DE-1.6 | Single-sheet adhesive workbook |
| `supplier_log` | DE-1.3 | Supplier delivery workbook |

After adding the entry, run the normal pipeline sequence — the new source
is picked up automatically by all scripts that handle its `seed_type`.

---

## 10. Idempotency and Retry

Every seed script is safe to re-run at any time:

- **Already complete** records in the DB are skipped
- **Partial records** (missing fields) are repaired
- **Failed operations** are logged to `logs/seed_failures.log`
- Re-running a script auto-detects the failures log and enters **retry mode**,
  processing only the previously failed items

```powershell
# Retry mode is automatic — just re-run the script
python -m seed.de_1_2_parse_specs

# Or force explicit retry
python -m seed.de_1_2_parse_specs --retry
```

On successful retry, the failure entries are removed from the log.

---

## 11. Logs

| File | Format | Purpose |
|------|--------|---------|
| `logs/seed_failures.log` | JSON lines | One entry per failed operation. Consumed (removed) on successful retry. |
| `logs/seed_audit.log` | JSON lines | Immutable before/after record for every threshold change applied by DE-1.4. |

**Failure entry structure:**
```json
{
  "script":    "de_1_1",
  "key":       "6MM",
  "reason":    "Header row not found",
  "detail":    "sheet=6MM",
  "timestamp": "2026-06-01T15:00:00Z"
}
```

**Audit entry structure:**
```json
{
  "script":    "de_1_4",
  "material":  "9mm MDF",
  "field":     "reorder_threshold",
  "old_value": null,
  "new_value": 500,
  "action":    "update",
  "timestamp": "2026-06-01T15:00:00Z"
}
```

---

## 12. Running Tests

```powershell
pytest tests/ -v
```

---

## 13. Known Source Data Issues

| Issue | Location | Impact | Status |
|-------|----------|--------|--------|
| Items column typo — `33mm` instead of `35mm` | 35MM tab, first data row | DE-1.1 reports unique-constraint conflict with 33MM tab; operation logged to `seed_failures.log` | Requires source correction in Excel |
| Three spec variants — `0.6*122*244`, `0.6*122*245`, `0.6*122*246` | 6MM tab, Specifications column | DE-1.2 logs as informational warning; canonical (first) spec used for properties | Acceptable; no action needed |
| Formula cells in balance column | All stock tabs | `data_only=True` returns `None`; these cells are excluded from seed | Expected behaviour |
| Blank first column in supplier header row | `Received tree logs trucks` sheet | Script skips null cells when reading headers; no data loss | Handled gracefully |
| `20MM` tab spec identical to `9MM` (`0.9*122*244`) | 20MM tab | Separate materials with same dimensions — correct, not a bug | No action needed |
