"""Rule-based reading of the multi-year results.

Every statement is derived from the calculated numbers (rank, change versus the previous year, period
average, sign). No external benchmarks are used: they would be arbitrary for a single insurer, so the text
describes what changed and what drives it, and leaves valuation to the analyst.
"""
from src.reporting.formatting import join_years, money, pct, pp


def _insight(level, key, es, en):
    return {"level": level, "key": key, "es": es, "en": en}


def _series(analysis, code):
    row = next((r for r in analysis.ratio_rows if r.spec.code == code), None)
    return {} if row is None else {y: v for y, v in row.values.items() if v is not None}


def _rank_text(values, year, high_is_good, lang):
    """Where `year` stands among the years (1 = highest)."""
    ordered = sorted(values, key=values.get, reverse=True)
    pos = ordered.index(year) + 1
    n = len(ordered)
    if lang == "es":
        if pos == 1:
            return "la más alta del periodo"
        if pos == n:
            return "la más baja del periodo"
        return f"la {pos}.ª más alta de {n} años"
    if pos == 1:
        return "the highest of the period"
    if pos == n:
        return "the lowest of the period"
    return f"#{pos} highest of {n} years"


def build_insights(analysis):
    years = analysis.years
    if len(years) < 2:
        return []
    last, prev = years[-1], years[-2]
    out = []
    s = analysis.summary

    # --- Sales
    prem = {y: s[y]["gross_premiums_written"] for y in years if s[y].get("gross_premiums_written")}
    if last in prem and prev in prem:
        g = prem[last] / prem[prev] - 1
        first = years[0]
        cagr = (prem[last] / prem[first]) ** (1 / (last - first)) - 1 if first in prem and last > first else None
        es = f"Las primas emitidas de {last} fueron {money(prem[last], 'es')} ({pct(g, 1, True)} vs {prev})"
        en = f"Written premiums in {last} were {money(prem[last], 'en')} ({pct(g, 1, True)} vs {prev})"
        if cagr is not None:
            es += f"; crecimiento compuesto de {pct(cagr)} anual desde {first}."
            en += f"; compound growth of {pct(cagr)} per year since {first}."
        else:
            es, en = es + ".", en + "."
        out.append(_insight("good" if g > 0 else "warn", "sales", es, en))

    # --- Net income
    ni = {y: s[y]["net_income"] for y in years if s[y].get("net_income") is not None}
    if last in ni and prev in ni and ni[prev]:
        ch = ni[last] / ni[prev] - 1
        out.append(_insight(
            "good" if ch >= 0 else "warn", "net_income",
            f"La utilidad neta de {last} fue {money(ni[last], 'es')} ({pct(ch, 1, True)} vs {prev}), "
            f"{_rank_text(ni, last, True, 'es')}.",
            f"Net income in {last} was {money(ni[last], 'en')} ({pct(ch, 1, True)} vs {prev}), "
            f"{_rank_text(ni, last, True, 'en')}."))

    # --- Technical result vs financial result
    tech = {y: s[y]["underwriting_result"] for y in years if s[y].get("underwriting_result") is not None}
    neg = [y for y, v in tech.items() if v < 0]
    rif = s[last].get("investment_financial_result")
    oper = s[last].get("operating_income")
    if neg:
        tail_es = tail_en = ""
        if last in neg and rif is not None and oper is not None:
            tail_es = (f" En {last} la operación (técnica y gastos) perdió {money(abs(oper), 'es')} y el resultado integral "
                       f"de financiamiento aportó {money(rif, 'es')}: la utilidad depende del rendimiento de las inversiones.")
            tail_en = (f" In {last} operations (underwriting and expenses) lost {money(abs(oper), 'en')} and the comprehensive "
                       f"financing result contributed {money(rif, 'en')}: profit relies on investment returns.")
        out.append(_insight(
            "bad" if last in neg else "warn", "technical",
            f"El resultado técnico fue negativo en {join_years(neg, 'es')}.{tail_es}",
            f"The technical result was negative in {join_years(neg, 'en')}.{tail_en}"))
    elif tech:
        out.append(_insight("good", "technical", "El resultado técnico fue positivo en todos los años analizados.",
                            "The technical result was positive in every analysed year."))

    # --- Claims ratio
    claims = _series(analysis, "claims_ratio")
    if last in claims and prev in claims:
        avg = sum(claims.values()) / len(claims)
        d = claims[last] - claims[prev]
        out.append(_insight(
            "bad" if d > 0.02 else ("good" if d < -0.02 else "info"), "claims",
            f"El costo de siniestros sobre primas devengadas fue {pct(claims[last])} en {last} ({pp(d)} vs {prev}); "
            f"el promedio del periodo es {pct(avg)}.",
            f"Net claims cost over earned premiums was {pct(claims[last])} in {last} ({pp(d)} vs {prev}); "
            f"the period average is {pct(avg)}."))

    # --- ROE
    roe = _series(analysis, "return_on_equity")
    if last in roe and prev in roe:
        avg = sum(roe.values()) / len(roe)
        d = roe[last] - roe[prev]
        out.append(_insight(
            "good" if d >= 0 else "warn", "roe",
            f"El ROE de {last} fue {pct(roe[last])} ({pp(d)} vs {prev}) frente a un promedio de {pct(avg)} en el periodo.",
            f"ROE in {last} was {pct(roe[last])} ({pp(d)} vs {prev}) against a period average of {pct(avg)}."))

    # --- Leverage
    lev = _series(analysis, "leverage_liabilities_to_equity")
    if lev:
        lo, hi = min(lev.values()), max(lev.values())
        reserves, liabilities = s[last].get("technical_reserves"), s[last].get("total_liabilities")
        share_es = share_en = ""
        if reserves and liabilities:
            share = reserves / liabilities
            share_es = f" Las reservas técnicas representan {pct(share)} del pasivo de {last}."
            share_en = f" Technical reserves represent {pct(share)} of {last} liabilities."
        out.append(_insight(
            "info", "leverage",
            f"El apalancamiento (pasivo / capital) se mantuvo entre {lo:.1f}x y {hi:.1f}x; en {last} fue {lev.get(last, float('nan')):.1f}x.{share_es}",
            f"Leverage (liabilities / equity) stayed between {lo:.1f}x and {hi:.1f}x; in {last} it was {lev.get(last, float('nan')):.1f}x.{share_en}"))

    # --- Reinsurance
    ret = _series(analysis, "retention_ratio")
    if last in ret:
        out.append(_insight(
            "info", "retention",
            f"La compañía retiene {pct(ret[last])} de la prima emitida y cede solo {pct(1 - ret[last])} al reaseguro.",
            f"The company retains {pct(ret[last])} of written premium and cedes only {pct(1 - ret[last])} to reinsurers."))

    # --- Combined ratio (supplementary engine ratio)
    comb = analysis.extras.get("combined_ratio_reference", {})
    if comb.get(last) is not None:
        c = comb[last]
        out.append(_insight(
            "bad" if c > 1 else "good", "combined",
            f"El índice combinado de referencia de {last} fue {pct(c)}: "
            + ("por encima de 100%, la suscripción no cubre siniestros y costos antes del resultado financiero."
               if c > 1 else "por debajo de 100%, la suscripción cubre siniestros y costos."),
            f"The reference combined ratio in {last} was {pct(c)}: "
            + ("above 100%, underwriting does not cover claims and costs before the financial result."
               if c > 1 else "below 100%, underwriting covers claims and costs.")))

    # --- Projection
    if analysis.sales is not None:
        ref = analysis.sales
        alts = [sc for sc in analysis.sales_scenarios if sc.key != "reference"]
        lo = min([ref.total] + [sc.total for sc in alts])
        hi = max([ref.total] + [sc.total for sc in alts])
        out.append(_insight(
            "info", "projection",
            f"Proyección de primas emitidas {ref.horizon_year}: {money(ref.total, 'es')} ({pct(ref.total_growth, 1, True)}) con el método del Excel; "
            f"los métodos alternos dan entre {money(lo, 'es')} y {money(hi, 'es')}.",
            f"Written-premium projection for {ref.horizon_year}: {money(ref.total, 'en')} ({pct(ref.total_growth, 1, True)}) with the workbook method; "
            f"alternative methods give between {money(lo, 'en')} and {money(hi, 'en')}."))

    # --- Data quality
    if analysis.checks:
        bad = [c for c in analysis.checks if c["status"] != "OK"]
        ok = len(analysis.checks) - len(bad)
        out.append(_insight(
            "good" if not bad else "bad", "quality",
            f"Verificaciones contables: {ok} de {len(analysis.checks)} cuadran (balance y estado de resultados)."
            + ("" if not bad else " Revisa la pestaña de datos."),
            f"Accounting checks: {ok} of {len(analysis.checks)} reconcile (balance sheet and income statement)."
            + ("" if not bad else " Review the data tab.")))
    return out
