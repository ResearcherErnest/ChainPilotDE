"""
DE-3: Ingest and catalog all client Excel datasets.

Loads each Excel file from Raw_data/, extracts sheet-level metadata,
and writes a structured catalog to data/catalog/catalog.json.
Raw files are never modified.

Usage:
    python -m etl.ingest_catalog
"""

import json
import os
import sys
from datetime import datetime

import openpyxl

_ROOT = os.path.dirname(os.path.dirname(__file__))
RAW_DATA_DIR = os.path.join(_ROOT, "Raw_data")
CATALOG_DIR = os.path.join(_ROOT, "data", "catalog")
CATALOG_PATH = os.path.join(CATALOG_DIR, "catalog.json")

SOURCES = [
    {
        "filename": "Stock management.xlsx",
        "source_id": "stock_management",
        "description": "Board material stock ledger — one tab per thickness (INPUT/OUTPUT/balance)",
    },
    {
        "filename": "GLUE RECORD-1.xlsx",
        "source_id": "glue_record",
        "description": "Glue stock ledger (INPUT/OUTPUT/balance)",
    },
    {
        "filename": "Tree log suppliers Book.xlsx",
        "source_id": "tree_log_suppliers",
        "description": "Supplier delivery records — summary + per-supplier tabs + received-trucks log",
    },
]


def profile_sheet(ws) -> dict:
    """Return basic metadata for a single worksheet."""
    rows = list(ws.iter_rows(values_only=True))
    total_rows = len(rows)
    non_empty_rows = sum(1 for r in rows if any(c is not None for c in r))
    col_count = ws.max_column or 0

    header_row = None
    for i, row in enumerate(rows):
        vals = [str(v).strip() for v in row if v is not None]
        if len(vals) >= 2:
            header_row = i + 1
            break

    return {
        "total_rows": total_rows,
        "non_empty_rows": non_empty_rows,
        "column_count": col_count,
        "header_row": header_row,
    }


def catalog_file(source: dict) -> dict:
    path = os.path.join(RAW_DATA_DIR, source["filename"])
    if not os.path.exists(path):
        return {
            **source,
            "status": "missing",
            "error": f"File not found: {path}",
            "sheets": [],
        }

    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    except Exception as exc:
        return {
            **source,
            "status": "error",
            "error": str(exc),
            "sheets": [],
        }

    sheets = []
    for name in wb.sheetnames:
        ws = wb[name]
        meta = profile_sheet(ws)
        sheets.append({"sheet_name": name, **meta})

    wb.close()

    file_size_kb = round(os.path.getsize(path) / 1024, 1)

    return {
        **source,
        "status": "ok",
        "path": os.path.relpath(path),
        "file_size_kb": file_size_kb,
        "sheet_count": len(sheets),
        "sheets": sheets,
    }


def main():
    os.makedirs(CATALOG_DIR, exist_ok=True)

    catalog = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "raw_data_dir": os.path.relpath(RAW_DATA_DIR),
        "sources": [],
    }

    for source in SOURCES:
        print(f"Cataloging {source['filename']} ...", end=" ")
        entry = catalog_file(source)
        catalog["sources"].append(entry)
        if entry["status"] == "ok":
            print(f"OK ({entry['sheet_count']} sheets, {entry['file_size_kb']} KB)")
        else:
            print(f"FAIL — {entry.get('error')}")

    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, default=str)

    print(f"\nCatalog written to {CATALOG_PATH}")


if __name__ == "__main__":
    main()
