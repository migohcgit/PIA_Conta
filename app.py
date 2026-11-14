"""Command line: analyse a folder (or list) of balance sheets / income statements and write the Excel report.

Examples
    python app.py "data/Seguros Monterrey"
    python app.py "data/Seguros Monterrey" --out resultados/analisis.xlsx --json resultados/analisis.json
"""
import argparse
import json
import sys
from pathlib import Path

from src.financial_engine.catalog import PCT, format_value
from src.orchestrator.multiyear import analyze_paths, discover_files
from src.reporting.excel_export import build_workbook
from src.reporting.formatting import money, pct


def main(argv=None):
    parser = argparse.ArgumentParser(description="Multi-year financial ratios, dashboard workbook and sales projection for insurers.")
    parser.add_argument("inputs", nargs="+", help="Folder(s) and/or statement files (PDF, XLSX, CSV)")
    parser.add_argument("--out", default="analisis_financiero.xlsx", help="Excel report to write")
    parser.add_argument("--json", help="Optional JSON result path")
    args = parser.parse_args(argv)

    paths = []
    for item in args.inputs:
        p = Path(item)
        paths += discover_files(p) if p.is_dir() else [p]
    if not paths:
        print("No statement files found.", file=sys.stderr)
        return 1
    analysis = analyze_paths(paths)
    if not analysis.years:
        print("No fiscal year could be identified.", file=sys.stderr)
        return 1

    print(f"{analysis.entity} · {analysis.years[0]}-{analysis.years[-1]}")
    print(f"{'Indicador':62}" + "".join(f"{y:>10}" for y in analysis.years))
    for row in analysis.ratio_rows:
        print(f"{row.spec.label_es[:61]:62}" + "".join(f"{format_value(row.values.get(y), row.spec.unit):>10}" for y in analysis.years))
    bad = [c for c in analysis.checks if c["status"] != "OK"]
    print(f"\nVerificaciones contables: {len(analysis.checks) - len(bad)}/{len(analysis.checks)} OK")
    for issue in analysis.issues:
        if issue.get("severity") != "info":
            print("  !", issue["message"])
    if analysis.sales:
        print(f"Proyección de primas emitidas {analysis.sales.horizon_year}: {money(analysis.sales.total)} ({pct(analysis.sales.total_growth, 1, True)})")
    if analysis.claims:
        print(f"Proyección de siniestralidad {analysis.claims.horizon_year}: {money(analysis.claims.total)} ({pct(analysis.claims.total_growth, 1, True)})")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(build_workbook(analysis))
    print(f"\nExcel: {out}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"JSON: {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
