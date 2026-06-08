"""
Schema registry — single source of truth for all backend schema definitions.

All de_2_x seed scripts import from here. To add a new UOM, category,
batch field, or attribute label: edit this file only — no script changes needed.

Target schema: ChainPilotBackend/modules/inventory/src/main/resources/
               db/migration/inventory/V1__create_inventory_item_registry.sql
"""

# ── Reference data ────────────────────────────────────────────────────────
# Mirrors com.chainpilot.inventory.shared.seeder.ReferenceDataSeeder exactly.
# Seeded by de_2_1 into the category and unit_of_measure tables.

CATEGORIES = [
    {
        "code":        "RAW_MATERIAL",
        "name":        "Raw Material",
        "description": "Unprocessed materials used in production",
    },
    {
        "code":        "CONSUMABLE",
        "name":        "Consumable",
        "description": "Items consumed during production or operations",
    },
    {
        "code":        "WIP",
        "name":        "Work In Progress",
        "description": "Items currently being processed",
    },
    {
        "code":        "FINISHED_GOOD",
        "name":        "Finished Good",
        "description": "Completed products ready for sale or dispatch",
    },
]

UNITS_OF_MEASURE = [
    {"code": "KG",    "label": "Kilogram"},
    {"code": "TONNE", "label": "Tonne"},
    {"code": "LITRE", "label": "Litre"},
    {"code": "M3",    "label": "Cubic Metre"},
    {"code": "PIECE", "label": "Piece"},
    {"code": "SHEET", "label": "Sheet"},
]

# ── Lookup shortcuts used by seed scripts ─────────────────────────────────

RAW_MATERIAL_CODE = "RAW_MATERIAL"

# Maps DE source config.base_uom strings → backend UOM code.
# "bags" uses PIECE because no BAG code exists in ReferenceDataSeeder.
UOM_CODE_MAP: dict[str, str] = {
    "sheets (pcs)": "SHEET",
    "bags":         "PIECE",
}

# ── MDF board batch fields ────────────────────────────────────────────────
# Inserted into batch_field_definition (one row per field per item).
# Source: Tree log suppliers Book — "Received tree logs trucks" sheet header row.
# Schema: batch_field_definition(item_id, code, label, data_type, is_required, sort_order)
# To add/remove a field: edit this list only — no script changes needed.

MDF_BATCH_FIELDS: list[dict] = [
    {"code": "date",              "label": "Date",                       "data_type": "date",    "is_required": True,  "sort_order": 1},
    {"code": "supplier_name",     "label": "Supplier name",              "data_type": "text",    "is_required": True,  "sort_order": 2},
    {"code": "plate_number",      "label": "Plate number",               "data_type": "text",    "is_required": True,  "sort_order": 3},
    {"code": "log_length_m",      "label": "Log length (m)",             "data_type": "decimal", "is_required": True,  "sort_order": 4},
    {"code": "wood_width_m",      "label": "Supplied Wood width (m)",    "data_type": "decimal", "is_required": True,  "sort_order": 5},
    {"code": "wood_length_m",     "label": "Supplied Wood length (m)",   "data_type": "decimal", "is_required": True,  "sort_order": 6},
    {"code": "total_m3",          "label": "Total cubed m3",             "data_type": "decimal", "is_required": False, "sort_order": 7},
    {"code": "unit_price_per_m3", "label": "Unit price per m3",          "data_type": "decimal", "is_required": True,  "sort_order": 8},
    {"code": "total_price",       "label": "Total price",                "data_type": "decimal", "is_required": False, "sort_order": 9},
    {"code": "unqualified_rwf",   "label": "Unqualified (Rwf)",          "data_type": "decimal", "is_required": False, "sort_order": 10},
    {"code": "return_out",        "label": "Return out",                 "data_type": "decimal", "is_required": False, "sort_order": 11},
    {"code": "balance_to_be_paid","label": "Balance to be paid",         "data_type": "decimal", "is_required": False, "sort_order": 12},
    {"code": "paid_amount",       "label": "Paid amount",                "data_type": "decimal", "is_required": False, "sort_order": 13},
    {"code": "payment_date",      "label": "Payment date",               "data_type": "date",    "is_required": False, "sort_order": 14},
    {"code": "payment_mode",      "label": "Payment Mode",               "data_type": "text",    "is_required": False, "sort_order": 15},
    {"code": "cheque_number",     "label": "Cheque number",              "data_type": "text",    "is_required": False, "sort_order": 16},
    {"code": "remaining_balance", "label": "Remaining balance",          "data_type": "decimal", "is_required": False, "sort_order": 17},
]

# ── Attribute label tuples ────────────────────────────────────────────────
# Stored in inventory_item.attributes JSONB.
# Format matches AttributeEntryRequest {label, value}.

# MDF board specs: parsed from "T*W*L" spec string (e.g. "0.9*122*244").
# Indices 0→Thickness, 1→Width, 2→Length.
MDF_ATTRIBUTE_LABELS: tuple[str, ...] = ("Thickness", "Width", "Length")

# Glue specs: parsed from "Nkg/Mbag" spec string (e.g. "25kg/1bag").
# Indices 0→weight, 1→bags.
GLUE_ATTRIBUTE_LABELS: tuple[str, ...] = ("Weight per bag (kg)", "Bags per unit")
