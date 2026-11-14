"""Multi-year pipeline: several fiscal years of balance sheets and income statements -> ratios + projections.

Flow (same layers as the single-period pipeline, applied per year)::

    detect + read PDFs -> align rows across years -> canonical data per year -> validation
    -> existing ratio engine -> ratio catalog (19 reference ratios) -> projections -> insights

The aligned statement tables are the single source of truth: manual corrections made in the UI are
written back into the tables, so ratios, charts and the Excel export always agree.
"""
import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

from src.financial_engine.catalog import CATALOG, RatioSpec
from src.financial_engine.insurer_ratios import calculate_insurer_ratios
from src.financial_engine.ratios import calculate_ratios
from src.forecasting import project_reference, project_scenarios
from src.ingestion.statement_meta import BALANCE, INCOME, detect_statement
from src.normalization.normalizer import canonicalize, normalize_label
from src.orchestrator.caller import _read
from src.orchestrator.statements import INCOME_KEYS
from src.validation.validator import validate_data

SUPPORTED = {".pdf", ".xlsx", ".xlsm", ".xls", ".csv"}
TOLERANCE_PESOS = 1.0  # statements are rounded to centavos; one peso absorbs rounding only

# Concepts shown in the dashboard / exported summary, in display order.
SUMMARY_KEYS = (
    "gross_premiums_written", "ceded_premiums", "retained_premiums", "technical_reserves_change",
    "net_premiums_earned", "acquisition_costs", "claims_incurred", "gross_claims_incurred",
    "underwriting_result", "operating_expenses_net", "operating_income", "investment_financial_result",
    "pre_tax_income", "income_tax", "net_income",
    "total_assets", "financial_investments", "technical_reserves", "total_liabilities", "total_equity",
    "paid_in_capital", "capital_reserve",
)

# Equivalent labels across fiscal years, used only to align rows in the full statement tables.
_ALIGN_SYNONYMS = {"otorgados": "dados", "intangibles amortizables": "amortizables"}


# --------------------------------------------------------------------------------------------------
# Aligned statement tables
# --------------------------------------------------------------------------------------------------
@dataclass
class TableRow:
    label: str
    key: str | None
    values: dict = field(default_factory=dict)  # year -> float | None


@dataclass
class StatementTable:
    kind: str
    years: list
    rows: list = field(default_factory=list)

    def first_row(self, key):
        return next((r for r in self.rows if r.key == key), None)

    def value(self, key, year):
        row = self.first_row(key)
        return None if row is None else row.values.get(year)

    def keyed_values(self, year):
        """Canonical key -> value for one year; the first row mapped to a key wins (duplicates are reported)."""
        out = {}
        for row in self.rows:
            if row.key and row.key not in out and row.values.get(year) is not None:
                out[row.key] = row.values[year]
        return out

    def set_value(self, key, year, value):
        row = self.first_row(key)
        if row is None:
            row = TableRow(label=key, key=key, values={})
            self.rows.append(row)
        row.values[year] = None if value is None else float(value)


def _slot(label, key):
    """Row identity used to line the same concept up across years."""
    base = key or normalize_label(label)
    if not key:
        for old, new in _ALIGN_SYNONYMS.items():
            base = base.replace(old, new)
        base = re.sub(r"^(los|las|el|la)\s+", "", base)
    return base


def build_table(kind, rows_by_year):
    """Align the extracted lines of several years into one table (rows in statement order)."""
    years = sorted(rows_by_year)
    slots_by_year, labels, keys = {}, {}, {}
    for year in years:
        seen, slots = {}, []
        for line in rows_by_year[year]:
            label = line.get("label", "")
            key = canonicalize(label)
            base = _slot(label, key)
            seen[base] = seen.get(base, 0) + 1
            slot = (base, seen[base])
            slots.append((slot, line["value"]))
            labels[slot] = label  # latest year's wording wins
            keys[slot] = key
        slots_by_year[year] = slots

    order = []
    for year in years:
        previous = None
        for slot, _ in slots_by_year[year]:
            if slot not in order:
                position = 0 if previous is None else order.index(previous) + 1
                order.insert(position, slot)
            previous = slot

    table = StatementTable(kind=kind, years=years)
    index = {}
    for slot in order:
        row = TableRow(label=labels[slot], key=keys[slot], values={y: None for y in years})
        table.rows.append(row)
        index[slot] = row
    for year in years:
        for slot, value in slots_by_year[year]:
            index[slot].values[year] = value
    return table


# --------------------------------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------------------------------
@dataclass
class Extraction:
    entity: str
    years: list
    balance: StatementTable
    income: StatementTable
    files: list = field(default_factory=list)   # [{name, kind, year, source, lines}]
    issues: list = field(default_factory=list)  # [{code, message, severity, year}]

    def copy(self):
        return copy.deepcopy(self)


def discover_files(folder, recursive=False):
    """List supported statement files in a folder (optionally including sub-folders)."""
    folder = Path(folder)
    iterator = folder.rglob("*") if recursive else folder.glob("*")
    return [p for p in sorted(iterator)
            if p.is_file() and p.suffix.lower() in SUPPORTED and not p.name.startswith((".", "~$"))]


def extract_statements(paths, names=None):
    """Read, classify and align a set of statement files.

    ``names`` optionally maps a path to the name shown to the user (uploaded files live in a temp folder).
    """
    names = names or {}
    issues, files, lines = [], [], {BALANCE: {}, INCOME: {}}
    entities = []
    for path in paths:
        display = names.get(str(path), Path(path).name)
        meta = detect_statement(path)
        if meta.kind is None or meta.year is None:
            issues.append({"code": "UNCLASSIFIED_FILE", "severity": "warning", "year": meta.year,
                           "message": f"No se pudo identificar tipo/año de «{display}»; se omitió."})
            continue
        if meta.year in lines[meta.kind]:
            issues.append({"code": "DUPLICATE_STATEMENT", "severity": "warning", "year": meta.year,
                           "message": f"Hay más de un {meta.kind} para {meta.year}; se conservó el primero («{display}» omitido)."})
            continue
        try:
            raw = _read(path)
        except Exception as exc:  # report and keep going with the remaining files
            issues.append({"code": "READ_ERROR", "severity": "error", "year": meta.year,
                           "message": f"No se pudo leer «{display}»: {exc}"})
            continue
        lines[meta.kind][meta.year] = raw
        files.append({"name": display, "kind": meta.kind, "year": meta.year, "source": meta.source, "lines": len(raw)})
        if meta.entity:
            entities.append(meta.entity)

    years = sorted(set(lines[BALANCE]) | set(lines[INCOME]))
    for year in years:
        for kind, label in ((BALANCE, "balance general"), (INCOME, "estado de resultados")):
            if year not in lines[kind]:
                issues.append({"code": "MISSING_STATEMENT", "severity": "warning", "year": year,
                               "message": f"Falta el {label} de {year}; las razones que lo requieren no se calcularán."})
    entity = max(set(entities), key=entities.count) if entities else "Aseguradora"
    entity = re.sub(r",?\s*S\.?A\.?.*$", "", entity, flags=re.I).strip().title() or entity
    return Extraction(entity=entity, years=years, balance=build_table(BALANCE, lines[BALANCE]),
                      income=build_table(INCOME, lines[INCOME]), files=files, issues=issues)


# --------------------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------------------
def _check(year, name, expected, actual, tolerance=TOLERANCE_PESOS):
    if expected is None or actual is None:
        return None
    diff = actual - expected
    return {"year": year, "check": name, "expected": expected, "actual": actual, "difference": diff,
            "status": "OK" if abs(diff) <= tolerance else "Revisar"}


def reconcile_year(data, year):
    """Accounting identities that must hold in a correctly extracted pair of statements."""
    g = data.get
    def part(*keys):
        vals = [g(k) for k in keys]
        return None if any(v is None for v in vals) else vals

    checks = []
    if (v := part("total_liabilities", "total_equity")) and g("total_assets") is not None:
        checks.append(_check(year, "Activo = Pasivo + Capital", sum(v), g("total_assets")))
    if (v := part("total_liabilities", "total_equity")) and g("total_liabilities_and_equity") is not None:
        checks.append(_check(year, "Suma del pasivo y capital = Pasivo + Capital", sum(v), g("total_liabilities_and_equity")))
    if (v := part("gross_premiums_written", "ceded_premiums")):
        checks.append(_check(year, "Primas emitidas − cedidas = retenidas", v[0] - v[1], g("retained_premiums")))
    if (v := part("retained_premiums", "technical_reserves_change")):
        checks.append(_check(year, "Primas retenidas − Δ reserva de riesgos en curso = devengadas", v[0] - v[1], g("net_premiums_earned")))
    if (v := part("net_premiums_earned", "acquisition_costs", "claims_incurred")):
        checks.append(_check(year, "Devengadas − adquisición − siniestros = resultado técnico", v[0] - v[1] - v[2], g("underwriting_result")))
    if g("underwriting_result") is not None and g("gross_profit") is not None:
        gross = g("underwriting_result") - (g("other_technical_reserves_change") or 0) + (g("analogous_operations_result") or 0)
        checks.append(_check(year, "Resultado técnico + operaciones análogas = utilidad bruta", gross, g("gross_profit")))
    if (v := part("gross_profit", "operating_expenses_net")):
        checks.append(_check(year, "Utilidad bruta − gastos de operación = utilidad de la operación", v[0] - v[1], g("operating_income")))
    if (v := part("operating_income", "investment_financial_result")):
        checks.append(_check(year, "Utilidad de la operación + RIF = utilidad antes de impuestos", v[0] + v[1], g("pre_tax_income")))
    if (v := part("pre_tax_income", "income_tax")):
        checks.append(_check(year, "Utilidad antes de impuestos − impuestos = utilidad neta", v[0] - v[1], g("net_income")))
    return [c for c in checks if c]


# --------------------------------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------------------------------
@dataclass
class RatioRow:
    spec: RatioSpec
    values: dict  # year -> float | None

    def to_dict(self):
        return {"category": self.spec.category, "indicator": self.spec.label_es, "unit": self.spec.unit_label_es,
                "values": {str(y): v for y, v in self.values.items()}}


@dataclass
class Analysis:
    entity: str
    years: list
    data: dict                 # year -> canonical concept -> value
    ratio_rows: list           # [RatioRow] in catalog order
    extras: dict               # engine ratio name -> {year: value} (not in the reference catalog)
    summary: dict              # year -> SUMMARY_KEYS -> value
    checks: list               # accounting reconciliation results
    issues: list
    proxies: list
    sales: object              # ReferenceProjection (written premiums)
    claims: object             # ReferenceProjection (net claims cost)
    sales_scenarios: list
    claims_scenarios: list
    extraction: Extraction

    def ratio(self, code, year):
        row = next((r for r in self.ratio_rows if r.spec.code == code), None)
        return None if row is None else row.values.get(year)

    def to_dict(self):
        return {
            "entity": self.entity, "years": self.years,
            "ratios": [r.to_dict() for r in self.ratio_rows],
            "summary": {str(y): v for y, v in self.summary.items()},
            "checks": self.checks, "issues": self.issues, "proxies": self.proxies,
            "projection_sales": self.sales.to_dict() if self.sales else None,
            "projection_claims": self.claims.to_dict() if self.claims else None,
            "sales_scenarios": [s.to_dict() for s in self.sales_scenarios],
        }


def canonical_data(extraction, year):
    """Merge balance and income values for one year (income statement wins for flow concepts)."""
    balance = extraction.balance.keyed_values(year)
    income = extraction.income.keyed_values(year)
    data = dict(balance)
    for key, value in income.items():
        if key in INCOME_KEYS or key not in data:
            data[key] = value
    return data


def _duplicate_issues(extraction):
    issues = []
    for table in (extraction.balance, extraction.income):
        for year in table.years:
            seen = {}
            for row in table.rows:
                if row.key and row.values.get(year) is not None:
                    seen.setdefault(row.key, []).append(row.label)
            for key, labels in seen.items():
                if len(labels) > 1:
                    issues.append({"code": "DUPLICATE_CONCEPT", "severity": "info", "year": year,
                                   "message": f"{year}: {len(labels)} filas se asignan a «{key}»; se usó la primera ({labels[0]})."})
    return issues


def analyze(extraction, overrides=None):
    """Run the full analysis on an extraction, optionally applying manual corrections.

    ``overrides`` maps ``year -> {canonical_key: amount}`` and is written back into the statement tables.
    """
    extraction = extraction.copy()
    for year, values in (overrides or {}).items():
        for key, amount in values.items():
            # Flow concepts live in the income statement; everything else in the balance sheet.
            in_income = extraction.income.first_row(key) is not None
            in_balance = extraction.balance.first_row(key) is not None
            table = extraction.income if in_income and (key in INCOME_KEYS or not in_balance) else extraction.balance
            table.set_value(key, int(year), amount)

    years = sorted(set(extraction.balance.years) | set(extraction.income.years))
    data, proxies, issues = {}, [], list(extraction.issues)
    for year in years:
        d = canonical_data(extraction, year)
        # CNSF statements label "Emitidas" as direct premium; when no explicit direct-premium line exists it is
        # used as the direct-premium proxy for the operating-cost ratio (documented, never silent).
        if "direct_premiums" not in d and "gross_premiums_written" in d:
            d["direct_premiums"] = d["gross_premiums_written"]
            proxies.append({"year": year, "concept": "direct_premiums", "source": "gross_premiums_written",
                            "note": "Prima directa aproximada con «Emitidas» (comisiones por reaseguro tomado = 0)."})
        data[year] = d
        for item in validate_data(d):
            if item["code"] in {"NO_DATA"}:
                issues.append({**item, "year": year})
            elif item["code"] != "BALANCE_SHEET_NOT_BALANCED":
                issues.append({**item, "message": f"{year}: {item['message']}", "year": year})

    checks = [c for y in years for c in reconcile_year(data[y], y)]
    for c in checks:
        if c["status"] != "OK":
            issues.append({"code": "RECONCILIATION", "severity": "warning", "year": c["year"],
                           "message": f"{c['year']}: «{c['check']}» no cuadra (diferencia {c['difference']:,.2f})."})
    issues.extend(_duplicate_issues(extraction))

    # --- ratio engine (existing modules), per year
    engine = {}
    for year in years:
        results = {r.name: r.value for r in calculate_ratios(data[year]) if r.value is not None}
        results.update({r.name: r.value for r in calculate_insurer_ratios(data[year]) if r.value is not None})
        engine[year] = results

    ratio_rows = [RatioRow(spec, {y: engine[y].get(spec.code) for y in years}) for spec in CATALOG]
    catalog_codes = {s.code for s in CATALOG}
    extra_names = sorted({n for y in years for n in engine[y]} - catalog_codes)
    extras = {n: {y: engine[y].get(n) for y in years} for n in extra_names}

    summary = {y: {k: data[y].get(k) for k in SUMMARY_KEYS} for y in years}

    def series(key):
        pairs = [(y, data[y].get(key)) for y in years if data[y].get(key) is not None]
        return [p[0] for p in pairs], [p[1] for p in pairs]

    sales = claims = None
    sales_sc = claims_sc = []
    sy, sv = series("gross_premiums_written")
    if len(sv) >= 2:
        sales, sales_sc = project_reference(sy, sv), project_scenarios(sy, sv)
    cy, cv = series("claims_incurred")
    if len(cv) >= 2:
        claims, claims_sc = project_reference(cy, cv), project_scenarios(cy, cv)
    if sales is None:
        issues.append({"code": "NO_PROJECTION", "severity": "warning", "year": None,
                       "message": "Se requieren al menos dos años con primas emitidas para proyectar ventas."})

    return Analysis(entity=extraction.entity, years=years, data=data, ratio_rows=ratio_rows, extras=extras,
                    summary=summary, checks=checks, issues=issues, proxies=proxies, sales=sales, claims=claims,
                    sales_scenarios=sales_sc, claims_scenarios=claims_sc, extraction=extraction)


def analyze_paths(paths, overrides=None, names=None):
    """Convenience wrapper: files -> Analysis."""
    return analyze(extract_statements(paths, names=names), overrides=overrides)


def analyze_folder(folder, overrides=None):
    return analyze_paths(discover_files(folder), overrides=overrides)
