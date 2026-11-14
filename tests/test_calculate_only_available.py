import unittest

from src.financial_engine.ratios import calculate_ratios
from src.financial_engine.insurer_ratios import calculate_insurer_ratios


class CalculateOnlyAvailableTests(unittest.TestCase):
    def test_generic_engine_omits_ratios_with_missing_inputs(self):
        results = calculate_ratios({
            "total_liabilities": 80,
            "total_assets": 100,
            "net_income": 10,
            "revenue": 50,
        })
        names = {ratio.name for ratio in results}
        self.assertIn("debt_to_assets", names)
        self.assertIn("net_profit_margin", names)
        self.assertNotIn("current_ratio", names)
        self.assertNotIn("cash_ratio", names)
        self.assertTrue(all(r.value is not None and r.status == "calculated" for r in results))

    def test_insurer_engine_does_not_use_proxy_values(self):
        results = {r.name: r for r in calculate_insurer_ratios({
            "operating_expenses_net": 10,
            "gross_premiums_written": 100,
            "claims_incurred": 30,
            "net_premiums_earned": 60,
        })}
        self.assertNotIn("operating_cost_ratio", results)
        self.assertNotIn("retained_claims_ratio", results)
        self.assertNotIn("combined_ratio_reference", results)
        self.assertIn("claims_ratio", results)
        self.assertTrue(all(r.value is not None and r.status == "calculated" for r in results.values()))

    def test_regulatory_ratios_are_omitted_when_inputs_missing(self):
        results = {r.name for r in calculate_insurer_ratios({
            "total_assets": 100, "total_liabilities": 80
        })}
        self.assertNotIn("guarantee_capital_coverage", results)
        self.assertNotIn("solvency_capital_to_gross_requirement", results)


if __name__ == "__main__":
    unittest.main()
