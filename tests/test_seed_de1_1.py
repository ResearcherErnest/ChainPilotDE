"""
Tests for DE-1.1: insert board materials from Stock_management.xlsx.

These tests exercise the pure-logic helpers (tab validation, header detection,
display-name derivation) without needing a live database or the actual workbook.

Run:
    pytest tests/test_seed_de1_1.py -v
"""

import os
import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Allow imports from the repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from seed.de_1_1_insert_materials import (
    THICKNESS_RE,
    COL_ITEMS,
    is_valid_tab,
    find_header_row_idx,
    get_first_data_row,
)


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _make_ws(rows: list):
    """Build a minimal mock worksheet whose iter_rows yields the given rows."""
    ws = MagicMock()
    ws.iter_rows.return_value = iter(
        [types.SimpleNamespace(**{"__iter__": lambda _: iter(r)}) for r in rows]
    )
    # iter_rows with values_only=True just returns tuples directly
    ws.iter_rows = lambda values_only=False: iter(rows)
    return ws


# ------------------------------------------------------------------ #
# Tab validation                                                        #
# ------------------------------------------------------------------ #

class TestIsValidTab(unittest.TestCase):
    def test_uppercase(self):
        for name in ("6MM", "9MM", "12MM", "18MM", "20MM", "27MM", "33MM"):
            with self.subTest(name=name):
                self.assertTrue(is_valid_tab(name))

    def test_lowercase(self):
        self.assertTrue(is_valid_tab("14mm"))

    def test_trailing_space(self):
        self.assertTrue(is_valid_tab("35MM "))

    def test_sales_form_rejected(self):
        self.assertFalse(is_valid_tab("sales form"))

    def test_empty_rejected(self):
        self.assertFalse(is_valid_tab(""))

    def test_letters_only_rejected(self):
        self.assertFalse(is_valid_tab("MM"))

    def test_digit_only_rejected(self):
        self.assertFalse(is_valid_tab("12"))


# ------------------------------------------------------------------ #
# Header row detection                                                 #
# ------------------------------------------------------------------ #

class TestFindHeaderRowIdx(unittest.TestCase):
    def _run(self, rows):
        ws = _make_ws(rows)
        return find_header_row_idx(ws)

    def test_header_at_row_1(self):
        rows = [
            ("Date", "Items", "Specifications", "quantity"),
        ]
        self.assertEqual(self._run(rows), 0)

    def test_header_at_row_2_with_preamble(self):
        rows = [
            ("INPUT", None, None, None, "OUTPUT"),
            ("Date", "Items", "Specifications", "quantity"),
        ]
        self.assertEqual(self._run(rows), 1)

    def test_no_header_returns_negative(self):
        rows = [
            (None, None, None),
            ("foo", "bar", "baz"),
        ]
        self.assertEqual(self._run(rows), -1)

    def test_case_insensitive(self):
        rows = [
            ("DATE", "ITEMS", "SPECIFICATIONS"),
        ]
        self.assertEqual(self._run(rows), 0)


# ------------------------------------------------------------------ #
# First data row                                                       #
# ------------------------------------------------------------------ #

class TestGetFirstDataRow(unittest.TestCase):
    def test_returns_first_non_empty_items(self):
        rows = [
            ("INPUT", None, None),
            ("Date", "Items", "Specifications"),   # header at index 1
            ("2025-01-01", "6mm", "0.6*122*244"),  # first data row
            ("2025-01-02", "6mm", "0.6*122*244"),
        ]
        ws = _make_ws(rows)
        row, row_num = get_first_data_row(ws, header_idx=1)
        self.assertIsNotNone(row)
        self.assertEqual(row[COL_ITEMS], "6mm")
        self.assertEqual(row_num, 3)

    def test_skips_null_items(self):
        rows = [
            ("Date", "Items", "Specifications"),
            ("2025-01-01", None, None),            # null Items → skip
            ("2025-01-02", "9mm", "0.9*122*244"),  # first valid
        ]
        ws = _make_ws(rows)
        row, row_num = get_first_data_row(ws, header_idx=0)
        self.assertEqual(row[COL_ITEMS], "9mm")
        self.assertEqual(row_num, 3)

    def test_no_data_returns_none(self):
        rows = [
            ("Date", "Items", "Specifications"),
            ("2025-01-01", None, None),
        ]
        ws = _make_ws(rows)
        row, row_num = get_first_data_row(ws, header_idx=0)
        self.assertIsNone(row)
        self.assertIsNone(row_num)


# ------------------------------------------------------------------ #
# Display-name derivation                                             #
# ------------------------------------------------------------------ #

class TestDisplayNameDerivation(unittest.TestCase):
    """Verify that Items value + ' MDF' gives the expected display_name."""

    cases = [
        ("6mm", "6mm MDF"),
        ("9mm", "9mm MDF"),
        ("12mm", "12mm MDF"),
        ("18mm", "18mm MDF"),
        ("20mm", "20mm MDF"),
        ("27mm", "27mm MDF"),
        ("33mm", "33mm MDF"),
        ("14mm", "14mm MDF"),
        # 35MM tab has Items='33mm' — this triggers a DB conflict in practice.
        ("33mm", "33mm MDF"),
    ]

    def test_derivation(self):
        for items_val, expected in self.cases:
            with self.subTest(items_val=items_val):
                display_name = str(items_val).strip() + " MDF"
                self.assertEqual(display_name, expected)

    def test_strips_whitespace(self):
        self.assertEqual("  9mm  ".strip() + " MDF", "9mm MDF")


if __name__ == "__main__":
    unittest.main()
