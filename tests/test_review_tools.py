import unittest

import pandas as pd

from src.interface.review_tools import rows_for_review, reviewed_values, reconcile


class ReviewToolsTests(unittest.TestCase):
    def test_unmapped_rows_remain_visible(self):
        rows = rows_for_review([{"label": "Unknown field", "value": 15, "source_location": "page:1"}])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows.iloc[0]["Include"])
        self.assertEqual(reviewed_values(rows), {})

    def test_duplicate_canonical_keys_are_rejected(self):
        frame = pd.DataFrame([
            {"Canonical key": "total_assets", "Amount": 10, "Include": True},
            {"Canonical key": "total_assets", "Amount": 20, "Include": True},
        ])
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            reviewed_values(frame)

    def test_balance_reconciliation(self):
        checks = reconcile({"total_assets": 100, "total_liabilities": 70, "total_equity": 30})
        self.assertEqual(checks[0]["Status"], "OK")


if __name__ == "__main__":
    unittest.main()
