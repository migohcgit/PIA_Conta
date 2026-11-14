import unittest
from src.financial_engine.ratios import safe_divide, calculate_ratios

class RatioTests(unittest.TestCase):
    def test_safe_divide_zero(self):
        self.assertIsNone(safe_divide(10, 0))

    def test_basic_ratio(self):
        data = {"current_assets": 200, "current_liabilities": 100}
        ratios = {r.name: r.value for r in calculate_ratios(data)}
        self.assertEqual(ratios["current_ratio"], 2)

    def test_combined_ratio(self):
        data = {"net_premiums_earned": 100, "claims_incurred": 60, "underwriting_expenses": 25}
        ratios = {r.name: r.value for r in calculate_ratios(data)}
        self.assertAlmostEqual(ratios["combined_ratio"], .85)

if __name__ == "__main__":
    unittest.main()
