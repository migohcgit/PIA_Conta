"""Pure view-model helpers (no Streamlit / Plotly imports) so they can be unit-tested."""
import html

import pandas as pd

from src.financial_engine.catalog import CATALOG, CATEGORIES, CATEGORY_EN, PCT, format_change, format_value
from src.reporting.formatting import money

KPI_CODES = (
    "return_on_equity", "return_on_assets", "net_margin_written_premiums", "technical_margin",
    "claims_ratio", "acquisition_cost_ratio", "leverage_liabilities_to_equity", "leverage_technical_reserves_to_equity",
)


def label_of(spec, lang):
    return spec.label_es if lang == "es" else spec.label_en


def short_of(spec, lang):
    return spec.short_es if lang == "es" else spec.short_en


def category_label(cat, lang):
    return cat if lang == "es" else CATEGORY_EN.get(cat, cat)


def tone(delta, direction):
    """good / bad / neutral for a change, given which direction is favourable."""
    if delta is None or direction is None or abs(delta) < 1e-12:
        return "neutral"
    return "good" if (delta > 0) == (direction == "up") else "bad"


def kpi_cards(analysis, year, compare, lang="es"):
    rows = {r.spec.code: r for r in analysis.ratio_rows}
    cards = []
    for code in KPI_CODES:
        row = rows[code]
        spec = row.spec
        a, b = row.values.get(year), row.values.get(compare)
        delta = None if a is None or b is None else a - b
        cards.append({
            "code": code, "label": short_of(spec, lang), "value": format_value(a, spec.unit, 1 if spec.unit == PCT else 2),
            "delta": format_change(delta, spec.unit) if delta is not None else "—",
            "tone": tone(delta, spec.direction), "compare": compare,
        })
    return cards


def kpi_html(card, vs_label="vs"):
    return (f'<div class="kpi"><div class="label">{html.escape(card["label"])}</div>'
            f'<div class="value">{html.escape(card["value"])}</div>'
            f'<div class="delta {card["tone"]}">{html.escape(card["delta"])}<span class="sub">{vs_label} {card["compare"]}</span></div></div>')


def insight_html(item, lang):
    return f'<div class="insight {item["level"]}">{html.escape(item[lang])}</div>'


def hero_html(analysis, lang, subtitle):
    chips = [f"{analysis.years[0]}–{analysis.years[-1]}", f"{len(analysis.years)} " + ("ejercicios" if lang == "es" else "fiscal years")]
    ok = sum(1 for c in analysis.checks if c["status"] == "OK")
    if analysis.checks:
        chips.append(f"{ok}/{len(analysis.checks)} " + ("verificaciones OK" if lang == "es" else "checks OK"))
    chips_html = "".join(f'<span class="chip">{html.escape(c)}</span>' for c in chips)
    return (f'<div class="hero"><h1>{html.escape(analysis.entity)}</h1><p>{html.escape(subtitle)}</p>'
            f'<div class="chips">{chips_html}</div></div>')


def bridge_data(analysis, year, t):
    """Waterfall from the technical result to net income (steps that cannot be derived are skipped)."""
    s = analysis.summary[year]
    d = analysis.data[year]
    tech, net = s.get("underwriting_result"), s.get("net_income")
    if tech is None or net is None:
        return []
    steps = [(t("bridge_technical"), tech, "relative")]
    gross = d.get("gross_profit")
    if gross is not None:
        steps.append((t("bridge_other"), gross - tech, "relative"))
    if s.get("operating_expenses_net") is not None:
        steps.append((t("bridge_opex"), -s["operating_expenses_net"], "relative"))
    if s.get("investment_financial_result") is not None:
        steps.append((t("bridge_rif"), s["investment_financial_result"], "relative"))
    if s.get("income_tax") is not None:
        steps.append((t("bridge_tax"), -s["income_tax"], "relative"))
    steps.append((t("bridge_net"), net, "total"))
    return steps


def balance_composition(analysis):
    out = []
    for y in analysis.years:
        s = analysis.summary[y]
        res, liab, eq = s.get("technical_reserves"), s.get("total_liabilities"), s.get("total_equity")
        if None in (res, liab, eq):
            continue
        out.append({"year": y, "reserves": res, "other": liab - res, "equity": eq})
    return out


def ratios_frame(analysis, lang="es"):
    """Wide table: category, indicator, unit, one column per year (decimals)."""
    rows = []
    for r in analysis.ratio_rows:
        rec = {"Categoría" if lang == "es" else "Category": category_label(r.spec.category, lang),
               "Indicador" if lang == "es" else "Indicator": label_of(r.spec, lang),
               "Unidad" if lang == "es" else "Unit": r.spec.unit_label_es if lang == "es" else ("Percent" if r.spec.unit == PCT else "Times")}
        for y in analysis.years:
            rec[str(y)] = r.values.get(y)
        rows.append(rec)
    return pd.DataFrame(rows)


def ratio_table_html(analysis, year, compare, lang="es", category=None):
    """HTML comparison table with the analysis year highlighted."""
    head = "".join(f'<th>{y}</th>' for y in analysis.years)
    out = [f'<table class="ratios"><tr><th>{"Indicador" if lang == "es" else "Indicator"}</th>{head}</tr>']
    for cat in CATEGORIES:
        if category not in (None, cat):
            continue
        out.append(f'<tr class="cat"><td colspan="{len(analysis.years) + 1}">{html.escape(category_label(cat, lang))}</td></tr>')
        for r in analysis.ratio_rows:
            if r.spec.category != cat:
                continue
            cells = ""
            for y in analysis.years:
                cls = ' class="sel"' if y == year else ""
                cells += f"<td{cls}>{format_value(r.values.get(y), r.spec.unit)}</td>"
            out.append(f"<tr><td>{html.escape(label_of(r.spec, lang))}</td>{cells}</tr>")
    out.append("</table>")
    return "".join(out)


def supplementary(analysis, year, t):
    items = []
    for code in ("operating_cost_ratio", "combined_ratio_reference", "premium_adequacy_with_financial_result"):
        v = analysis.extras.get(code, {}).get(year)
        if v is not None:
            items.append((t(code), format_value(v, PCT, 1)))
    return items


def amounts_frame(analysis, lang, keys, label_fn):
    """Key concepts × years in pesos, for the editable table."""
    rows = []
    for k in keys:
        rec = {"key": k, label_fn("concept"): label_fn(k)}
        for y in analysis.years:
            rec[str(y)] = analysis.data[y].get(k)
        rows.append(rec)
    return pd.DataFrame(rows)


def overrides_from_edit(original, edited, years, tol=0.005):
    """Changed cells between two frames -> {year: {key: amount}}."""
    out = {}
    for i in range(len(original)):
        key = original.iloc[i]["key"]
        for y in years:
            a, b = original.iloc[i][str(y)], edited.iloc[i][str(y)]
            if pd.isna(b):
                continue
            if pd.isna(a) or abs(float(a) - float(b)) > tol:
                out.setdefault(int(y), {})[key] = float(b)
    return out


def merge_overrides(base, new):
    merged = {y: dict(v) for y, v in (base or {}).items()}
    for y, vals in new.items():
        merged.setdefault(y, {}).update(vals)
    return merged
