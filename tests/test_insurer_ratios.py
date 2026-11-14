import unittest
from src.financial_engine.insurer_ratios import calculate_insurer_ratios


class InsurerRatioTests(unittest.TestCase):
    def test_combined_ratio_calculates_only_when_all_components_are_available(self):
        data = {
            "operating_expenses_net": 10,
            "direct_premiums": 100,
            "acquisition_costs": 20,
            "retained_premiums": 80,
            "claims_incurred": 30,
            "net_premiums_earned": 60,
        }
        results = {r.name: r for r in calculate_insurer_ratios(data)}
        expected = 10 / 100 + 20 / 80 + 30 / 60
        self.assertAlmostEqual(results["combined_ratio_reference"].value, expected)
        self.assertAlmostEqual(results["premium_adequacy"].value, 1 - expected)

    def test_regulatory_ratio_is_omitted_without_inputs(self):
        results = {r.name for r in calculate_insurer_ratios({"total_assets": 100, "total_liabilities": 80})}
        self.assertNotIn("guarantee_capital_coverage", results)
        self.assertNotIn("solvency_capital_to_gross_requirement", results)

    def test_direct_premiums_are_not_substituted_with_written_premiums(self):
        results = {r.name for r in calculate_insurer_ratios({
            "operating_expenses_net": 10,
            "gross_premiums_written": 100,
        })}
        self.assertNotIn("operating_cost_ratio", results)

    def test_retained_claims_are_not_substituted_with_claims_incurred(self):
        results = {r.name for r in calculate_insurer_ratios({
            "claims_incurred": 30,
            "net_premiums_earned": 60,
        })}
        self.assertNotIn("retained_claims_ratio", results)


if __name__ == "__main__":
    unittest.main()
