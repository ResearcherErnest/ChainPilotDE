# ChainPilot — Data Engineering

Local data engineering workspace for the ChainPilot inventory system.
Handles ingestion, profiling, schema mapping, and migration seeding of client Excel datasets.

## Prerequisites

- Python 3.11+
- PostgreSQL 14+ (the ChainPilot application's test database)
- Virtual environment (`.venv/` already initialised in this repo)

## Setup

```bash
# 1. Activate the virtual environment
.venv\Scripts\activate          # Windows PowerShell
source .venv/bin/activate       # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure the database connection
copy .env.example .env          # Windows
cp .env.example .env            # macOS / Linux
# Edit .env and set DATABASE_URL

# 4. (First time) create the test database schema
python -m seed.db_setup
```

## Project Structure

```
ChainPilotDE/
├── Raw_data/                          # Immutable client Excel source files — never modify
│   ├── Stock management.xlsx
│   ├── GLUE RECORD-1.xlsx
│   └── Tree log suppliers Book.xlsx
│
├── data/                              # All data workspace outputs (grouped by purpose)
│   ├── raw/                           # Placeholder — source files live in Raw_data/
│   ├── staging/                       # Intermediate transformed outputs
│   ├── catalog/                       # Ingest catalog (catalog.json)
│   └── profiles/                      # Data quality reports (data_quality_report.json)
│
├── etl/                               # Ingestion and profiling scripts
│   ├── ingest_catalog.py              # DE-3: catalog all Excel sources with metadata
│   └── profile_data.py               # DE-4: profile data quality (nulls, duplicates, types)
│
├── notebooks/                         # Jupyter exploration notebooks
│   └── 01_data_exploration.ipynb
│
├── docs/                              # Mapping and design documents
│   └── source_target_mapping.md      # DE-5/DE-6: source-to-target field mapping
│
├── seed/                              # DB migration seed scripts (run in order)
│   ├── db.py                          # Shared DB connection helper
│   ├── seed_logger.py                 # Failure and audit log management
│   ├── db_setup.py                    # Create test database schema
│   ├── thresholds.json                # Version-controlled reorder thresholds
│   ├── de_1_1_insert_materials.py     # DE-1.1: insert one material per stock tab
│   ├── de_1_2_parse_specs.py          # DE-1.2: parse specs → insert dimension properties
│   ├── de_1_3_insert_batch_fields.py  # DE-1.3: read supplier headers → insert batch fields
│   └── de_1_4_apply_thresholds.py     # DE-1.4: apply reorder thresholds from config
│
├── logs/                              # Runtime logs (gitignored except placeholder)
│   ├── seed_failures.log              # Failed operations — JSON lines, consumed on retry
│   └── seed_audit.log                 # Audit trail for threshold updates — append-only
│
├── tests/                             # pytest test suite
│   └── test_seed_de1_1.py
│
├── .env.example                       # Environment variable template
├── requirements.txt
└── stories.md                         # User stories and acceptance criteria
```

## Running the ETL Scripts

```bash
# DE-3: Ingest and catalog all Excel sources
python -m etl.ingest_catalog
# Output → data/catalog/catalog.json

# DE-4: Profile data quality
python -m etl.profile_data
# Output → data/profiles/data_quality_report.json
```

## Running the Seed Scripts

Run in dependency order. Each script is **idempotent** — safe to re-run at any time.

```bash
# Step 1 — DE-1.1: Insert one material record per thickness tab
python -m seed.de_1_1_insert_materials

# Step 2 — DE-1.2: Parse spec strings and attach dimension properties
python -m seed.de_1_2_parse_specs

# Step 3 — DE-1.3: Read supplier workbook headers, insert batch field definitions
python -m seed.de_1_3_insert_batch_fields

# Step 4 — DE-1.4: Apply reorder thresholds from thresholds.json
python -m seed.de_1_4_apply_thresholds
```

### Retry after partial failure

If any script reports failures, inspect `logs/seed_failures.log`.
Re-running the same script automatically enters **retry mode** — it processes
only the previously failed items and removes them from the log on success:

```bash
python -m seed.de_1_1_insert_materials          # auto-detects failures log → retry mode
python -m seed.de_1_1_insert_materials --retry  # explicit retry flag
```

## Logs

| File | Purpose |
|------|---------|
| `logs/seed_failures.log` | JSON lines — one entry per failed operation. Consumed on successful retry. |
| `logs/seed_audit.log` | JSON lines — immutable before/after record for all threshold changes. |

## Running Tests

```bash
pytest tests/ -v
```

## Source Data Notes

| Issue | Location | Impact |
|-------|----------|--------|
| Items column typo (`33mm` instead of `35mm`) | 35MM tab | DE-1.1 reports a unique-constraint conflict; logged to `seed_failures.log` |
| Three spec variants (`0.6*122*244/245/246`) | 6MM tab | DE-1.2 logs as informational warning; canonical spec used for properties |
| Formula cells in balance column | All stock tabs | `data_only=True` returns `None`; excluded from seed |
| Blank first column in supplier sheet | Received tree logs trucks | Script skips blank cells when reading header row |
