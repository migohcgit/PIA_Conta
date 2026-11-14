"""Acceptance tests: the multi-year pipeline must reproduce the reference workbook PIA_AnálisisFinanciero.xlsx."""
import glob
import io
import unittest
import warnings
from pathlib import Path

import openpyxl

from src.forecasting import project_reference, project_scenarios
from src.ingestion.pdf_reader import _line_to_item
from src.ingestion.statement_meta import BALANCE, INCOME, detect_statement
from src.orchestrator.multiyear import analyze, analyze_folder, discover_files, extract_statements
from src.reporting.excel_export import build_workbook

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "Seguros Monterrey"
REF = next(iter(glob.glob(str(ROOT / "data" / "*.xlsx"))), None)
needs_data = unittest.skipUnless(DATA.exists() and REF, "bundled data and reference workbook required")


class ParserTests(unittest.TestCase):
    def test_first_amount_wins_over_stray_trailing_figure(self):
        item = _line_to_item("UTILIDAD (PÉRDIDA) DEL EJERCICIO 3,986,372,929.59 0.00", "x")
        self.assertEqual(item["label"], "UTILIDAD (PÉRDIDA) DEL EJERCICIO")
        self.assertEqual(item["value"], 3986372929.59)

    def test_period_headers_and_footers_are_not_line_items(self):
        self.assertIsNone(_line_to_item("DEL 1 DE ENERO AL 31 DE DICIEMBRE DE 2025", "x"))
        self.assertIsNone(_line_to_item("Ciudad de México, a 24 de febrero de 2026", "x"))
        self.assertIsNone(_line_to_item("al cierre del ejercicio de 2025", "x"))

    def test_negative_parenthesis_amounts(self):
        self.assertEqual(_line_to_item("(-) Cedidas (1,170.50)", "x")["value"], -1170.5)


@needs_data
class DetectionTests(unittest.TestCase):
    def test_kind_year_and_entity_from_header(self):
        meta = detect_statement(DATA / "balance-general-consolidado-2022.pdf")
        self.assertEqual((meta.kind, meta.year, meta.source), (BALANCE, 2022, "header"))
        meta = detect_statement(DATA / "estado-de-resultados-consolidado-2021.pdf")
        self.assertEqual((meta.kind, meta.year), (INCOME, 2021))
        self.assertIn("monterrey", meta.entity.lower())


@needs_data
class ReferenceWorkbookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analysis = analyze_folder(DATA)
        cls.ref = openpyxl.load_workbook(REF, data_only=True)

    def test_five_years_and_all_statements_found(self):
        self.assertEqual(self.analysis.years, [2021, 2022, 2023, 2024, 2025])
        self.assertEqual(len(self.analysis.extraction.files), 10)

    def test_all_accounting_checks_pass(self):
        self.assertGreaterEqual(len(self.analysis.checks), 40)
        self.assertEqual([c for c in self.analysis.checks if c["status"] != "OK"], [])

    def test_every_ratio_matches_comparativo(self):
        ws, compared = self.ref["COMPARATIVO"], 0
        for r in range(5, 24):
            row = next(x for x in self.analysis.ratio_rows if x.spec.label_es == ws.cell(r, 2).value)
            for j, year in enumerate(self.analysis.years):
                self.assertAlmostEqual(row.values[year], ws.cell(r, 4 + j).value, places=9, msg=f"{row.spec.label_es} {year}")
                compared += 1
        self.assertEqual(compared, 95)

    def test_income_statement_matches_base_er(self):
        ws = self.ref["BASE_ER"]
        nonzero = lambda rows: [tuple(round(v or 0, 2) for v in r) for r in rows if any(abs(v or 0) > 0 for v in r)]
        expected = nonzero([[ws.cell(r, c).value for c in range(2, 7)] for r in range(5, 58) if ws.cell(r, 2).value is not None])
        got = nonzero([[row.values[y] for y in self.analysis.years] for row in self.analysis.extraction.income.rows])
        self.assertEqual(got, expected)

    def test_projections_match_reference(self):
        sales, claims = self.analysis.sales, self.analysis.claims
        self.assertAlmostEqual(sales.total, self.ref["PROYECCIÓN_VENTAS"]["B26"].value, places=2)
        self.assertAlmostEqual(sales.mean_growth, self.ref["PROYECCIÓN_VENTAS"]["B9"].value, places=12)
        self.assertAlmostEqual(claims.total, self.ref["SINIESTRALIDAD"]["B28"].value, places=2)
        self.assertEqual(sales.horizon_year, 2026)

    def test_manual_correction_flows_to_ratios_and_flags_inconsistency(self):
        extraction = extract_statements(discover_files(DATA))
        fixed = analyze(extraction, {2025: {"net_income": 3_000_000_000}})
        self.assertAlmostEqual(fixed.ratio("return_on_equity", 2025), 3_000_000_000 / fixed.data[2025]["total_equity"])
        self.assertTrue(any(c["status"] != "OK" for c in fixed.checks))
        self.assertEqual(analyze(extraction).ratio("return_on_equity", 2024), self.analysis.ratio("return_on_equity", 2024))


class ProjectionTests(unittest.TestCase):
    def test_reference_method_steps(self):
        p = project_reference([2021, 2022, 2023], [100.0, 110.0, 121.0])
        self.assertAlmostEqual(p.mean_growth, 0.10)
        self.assertAlmostEqual(p.monthly_rate, 0.10 / 12)
        self.assertAlmostEqual(p.monthly_base, 121 / 12)
        self.assertAlmostEqual(p.months[0].value, 121 / 12 * (1 + 0.10 / 12))
        self.assertAlmostEqual(p.total, sum(m.value for m in p.months))
        self.assertEqual(len(p.months), 12)

    def test_scenarios_include_reference_and_linear_trend(self):
        sc = {s.key: s for s in project_scenarios([2021, 2022, 2023], [100.0, 110.0, 120.0])}
        self.assertAlmostEqual(sc["linear"].total, 130.0)
        self.assertEqual(set(sc), {"reference", "annual_mean", "cagr", "linear"})

    def test_needs_two_years(self):
        with self.assertRaises(ValueError):
            project_reference([2025], [1.0])


@needs_data
class ExcelExportTests(unittest.TestCase):
    def test_workbook_structure_formulas_and_cached_values(self):
        analysis = analyze_folder(DATA)
        wb = openpyxl.load_workbook(io.BytesIO(build_workbook(analysis)))
        self.assertEqual(wb.sheetnames, ["COMPARATIVO", "DASHBOARD INTERACTIVO", "PROYECCIÓN_VENTAS", "SINIESTRALIDAD",
                                         "VALIDACIÓN", "LISTAS", "BASE_ER", "BASE_BG"])
        self.assertTrue(str(wb["COMPARATIVO"]["D5"].value).startswith("=IFERROR("))
        cached = openpyxl.load_workbook(io.BytesIO(build_workbook(analysis)), data_only=True)
        self.assertAlmostEqual(cached["PROYECCIÓN_VENTAS"]["B26"].value, analysis.sales.total, places=2)
        self.assertAlmostEqual(cached["COMPARATIVO"]["H17"].value, analysis.ratio("return_on_equity", 2025), places=9)


if __name__ == "__main__":
    unittest.main()
