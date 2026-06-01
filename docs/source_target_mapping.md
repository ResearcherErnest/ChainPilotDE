# ChainPilot — Source-to-Target Data Mapping

**Version:** 1.1  
**Prepared:** 2026-05-29  
**Updated:** 2026-06-01  
**Scope:** Stock Management, GLUE RECORD-1, Tree Log Suppliers Book  

---

## 1. Source Files

| File | Sheets | Description |
|------|--------|-------------|
| `Stock management.xlsx` | 6MM, 9MM, 12MM, 18MM, 20MM, 27MM, 33MM, 35MM, 14mm, sales form | Board material INPUT/OUTPUT stock ledger |
| `GLUE RECORD-1.xlsx` | GLUE A , B, C and D | Glue consumable INPUT/OUTPUT ledger |
| `Tree log suppliers Book.xlsx` | Production summary, Received tree logs trucks, (supplier tabs ×22) | Supplier delivery and payment records |

---

## 2. Target Schema (Test Database)

```
inventory_item          — material catalogue
item_property           — per-material dimension properties
batch_field             — per-material intake form field definitions
```

---

## 3. Stock Management → `inventory_item` + `item_property`

### 3.1 Tab → `inventory_item` (DE-1.1)

One record inserted per valid thickness tab (skip `sales form`).

| Source | Source Field | Target Table | Target Column | Transformation |
|--------|-------------|--------------|---------------|----------------|
| Tab name | (sheet name) | `inventory_item` | — | Used for tab selection only |
| Items column, row 3+ | `Items` | `inventory_item` | `display_name` | `trim(Items) + " MDF"` |
| Hardcoded | — | `inventory_item` | `category` | `"Raw Material"` |
| Hardcoded | — | `inventory_item` | `base_uom` | `"sheets (pcs)"` |
| `thresholds.json` | — | `inventory_item` | `reorder_threshold` | Applied by DE-1.4; null if not listed |

**Valid tabs (9):** 6MM, 9MM, 12MM, 18MM, 20MM, 27MM, 33MM, 35MM, 14mm  
**Skipped tabs:** `sales form` (name does not match `\d+[Mm]{2}` pattern)

**Known data quality issues:**

| Tab | Issue | Impact |
|-----|-------|--------|
| 35MM | `Items` column contains `'33mm'` (should be `'35mm'`) | DE-1.1 will attempt to insert `'33mm MDF'`, conflicting with the 33MM tab. Logged as failure in `seed_failures.log`. Requires source correction or manual override. |
| 20MM | `Specifications` = `'0.9*122*244'` (same as 9MM) | Separate inventory_item; different material despite identical spec string. |

### 3.2 Specifications Column → `item_property` (DE-1.2)

One set of three properties per material, parsed from the `Specifications` column.

| Source | Source Field | Target Table | Target Column | Transformation |
|--------|-------------|--------------|---------------|----------------|
| Specifications, first non-null | e.g. `"0.9*122*244"` | `item_property` | `property_name = 'thickness'` | `split("*")[0]` → Decimal |
| Specifications, first non-null | e.g. `"0.9*122*244"` | `item_property` | `property_name = 'width'` | `split("*")[1]` → Decimal |
| Specifications, first non-null | e.g. `"0.9*122*244"` | `item_property` | `property_name = 'length'` | `split("*")[2]` → Decimal |

**Specification strings by tab:**

| Tab | Canonical Spec | Thickness (m) | Width (mm) | Length (mm) | Variants |
|-----|---------------|---------------|-----------|------------|---------|
| 6MM | `0.6*122*244` | 0.6 | 122 | 244 | `0.6*122*245`, `0.6*122*246` |
| 9MM | `0.9*122*244` | 0.9 | 122 | 244 | — |
| 12MM | `1.2*122*244` | 1.2 | 122 | 244 | — |
| 18MM | `1.8*122*244` | 1.8 | 122 | 244 | — |
| 20MM | `0.9*122*244` | 0.9 | 122 | 244 | — |
| 27MM | `2.7*122*244` | 2.7 | 122 | 244 | — |
| 33MM | `3.3*122*244` | 3.3 | 122 | 244 | — |
| 35MM | `3.5*122*244` | **3.5** (not 35) | 122 | 244 | — |
| 14mm | `1.4*122*244` | 1.4 | 122 | 244 | — |

> Note: The 35MM tab spec correctly uses `3.5` (metres). The Items column typo (`33mm`) is separate from this.

---

## 4. Tree Log Suppliers Book → `batch_field` (DE-1.3)

Source: `Received tree logs trucks` sheet, header row (row 4).

Each column maps to a `batch_field` record inserted against **every** board material.

| Source Column Header | `field_key` | `field_type` | `is_required` | Notes |
|---------------------|-------------|-------------|--------------|-------|
| Date | `date` | date | Yes | — |
| Supplier name | `supplier_name` | text | Yes | — |
| Plate number | `plate_number` | text | Yes | — |
| Log length (m) | `log_length_m` | decimal | Yes | — |
| Supplied Wood width (m) | `wood_width_m` | decimal | Yes | — |
| Supplied Wood length (m) | `wood_length_m` | decimal | Yes | — |
| Total cubed m3 | `total_m3` | decimal | No | Computed |
| Unit price per m3 | `unit_price_per_m3` | decimal | Yes | — |
| Total price | `total_price` | decimal | No | Computed |
| Unqualified (Rwf) | `unqualified_rwf` | decimal | No | — |
| Return out | `return_out` | decimal | No | — |
| Balance to be paid | `balance_to_be_paid` | decimal | No | Computed |
| Paid amount | `paid_amount` | decimal | No | — |
| Payment date | `payment_date` | date | No | — |
| Payment Mode | `payment_mode` | text | No | — |
| Cheque number | `cheque_number` | text | No | — |
| Remaining balance | `remaining_balance` | decimal | No | Computed |

> The header row in the workbook has a blank first cell (column A). Headers start at column B. `Supplier name` has a trailing space in the source — the script strips all headers before matching.

---

## 5. GLUE RECORD-1 → `inventory_item` + `item_property` (DE-1.5, DE-1.6)

Sheet: `GLUE A , B, C and D`

The sheet follows the same INPUT/OUTPUT/balance structure as the stock management tabs
with a header row at row 2 (Date, Items, Specifications, quantity, ...).

### 5.1 Material → `inventory_item` (DE-1.5)

| Source | Source Field | Target Table | Target Column | Transformation |
|--------|-------------|--------------|---------------|----------------|
| Items column, first data row | `"glue"` | `inventory_item` | `display_name` | `title()` → `"Glue"` |
| Hardcoded | — | `inventory_item` | `category` | `"Raw Material"` |
| config.SOURCES entry | `base_uom` | `inventory_item` | `base_uom` | `"bags"` |

DE-1.5 is **config-driven**: it loops over all sources with `seed_type="glue_ledger"`
in `config.py`. Adding a new adhesive workbook requires only a new `SOURCES` entry —
no script changes.

### 5.2 Specifications → `item_property` (DE-1.6)

Spec format: `"<weight>kg/<count>bag"` (e.g. `"25kg/1bag"`)

| Source | Source Field | Target Table | Target Column | Transformation |
|--------|-------------|--------------|---------------|----------------|
| Specifications column, first data row | `"25kg/1bag"` | `item_property` | `property_name = 'weight_per_bag_kg'` | regex → Decimal(`25`) |
| Specifications column, first data row | `"25kg/1bag"` | `item_property` | `property_name = 'bags_per_unit'` | regex → Decimal(`1`) |

**Current values:**

| Material | Spec | `weight_per_bag_kg` | `bags_per_unit` |
|----------|------|---------------------|-----------------|
| Glue | `25kg/1bag` | 25.0 | 1.0 |

---

## 6. Reorder Thresholds (DE-1.4)

Source: `seed/thresholds.json` (version-controlled).

| `display_name` | `reorder_threshold` |
|----------------|---------------------|
| 9mm MDF | 500 |
| 6mm MDF | 300 |
| 12mm MDF | 200 |
| All others | null (no threshold set) |

---

## 7. Unmapped / Ambiguous Fields

| Source Field | Reason Unmapped | Resolution |
|-------------|-----------------|------------|
| `balance` column (stock tabs) | Formula cell — value computed by Excel, not stored | Recompute from INPUT/OUTPUT totals in ETL if needed |
| `sales form` sheet | Out of scope for material catalogue seed | Future sprint — maps to sales order entity |
| Per-supplier tabs (22 tabs) | Individual supplier accounts, not batch metadata | Future sprint — maps to supplier entity |
| `Cheque number` in supplier tabs | Same semantic as `batch_field.cheque_number` | Consistent; no conflict |

---

## 8. Data Type Mismatches

| Source | Field | Source Type | Target Type | Resolution |
|--------|-------|-------------|-------------|-----------|
| Specifications | All segments | String (`"0.9*122*244"`) | `NUMERIC(12,4)` | Split on `*`, cast each segment via `Decimal()` |
| Dates | All date columns | `datetime` object (openpyxl) | `TIMESTAMPTZ` | psycopg2 handles automatically |
| Balance | `balance` column | Excel formula string | — | Excluded from seed |
| `Total cubed m3` | Some rows | Formula string | `NUMERIC` | `data_only=True` suppresses formula; treat as null if not a number |
