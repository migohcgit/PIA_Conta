"""Financial overview and exploratory charts for insurer analysis."""

import pandas as pd
import streamlit as st


GROUPS = {
    "Liquidity": ["current_ratio", "cash_ratio", "liquidity_current", "liquidity_available_to_exigible", "liquidity_current_to_exigible", "liquidity_current_to_technical_reserves", "liquidity_investments_to_current_liabilities"],
    "Solvency": ["debt_to_assets", "equity_ratio", "solvency_total_assets_to_liabilities", "solvency_capital_to_gross_requirement", "guarantee_capital_coverage", "solvency_margin_to_guarantee_capital", "solvency_adjusted_assets", "leverage_liabilities_to_equity", "leverage_technical_reserves_to_equity"],
    "Profitability": ["net_profit_margin", "return_on_assets", "return_on_equity", "return_on_equity_reference", "investment_yield", "technical_margin", "adjusted_roa", "adjusted_roe", "net_margin_written_premiums"],
    "Underwriting": ["operating_cost_ratio", "acquisition_cost_ratio", "claims_ratio", "combined_ratio_reference", "premium_adequacy", "retention_ratio", "ceded_premium_ratio", "retained_claims_ratio"],
}

KEY_METRICS = [
    ("liquidity_current", "Liquidez corriente", "Current liquidity", False),
    ("solvency_total_assets_to_liabilities", "Cobertura del pasivo", "Liability coverage", False),
    ("return_on_equity", "Rentabilidad del capital", "Return on equity", True),
    ("combined_ratio_reference", "Índice combinado", "Combined ratio", True),
]


def _number(value, percent=False):
    return f"{value * 100:,.1f}%" if percent else f"{value:,.2f}x"


def _assessment(values, lang):
    notes = []
    def add(condition, es, en):
        if condition:
            notes.append(es if lang == "es" else en)

    liquidity = values.get("liquidity_current", values.get("current_ratio"))
    if liquidity is not None:
        add(liquidity < 1, "La liquidez corriente es inferior a 1: los activos circulantes no cubren completamente el pasivo circulante.", "Current liquidity is below 1: current assets do not fully cover current liabilities.")
        add(liquidity >= 1, "Los activos circulantes cubren el pasivo circulante según las cifras reportadas.", "Current assets cover current liabilities based on reported figures.")
    debt = values.get("debt_to_assets")
    if debt is not None:
        add(debt > 0.8, "El pasivo representa más del 80% de los activos; conviene revisar la composición de reservas y capital.", "Liabilities exceed 80% of assets; review reserve composition and capital adequacy.")
    income = values.get("return_on_equity", values.get("return_on_equity_reference"))
    if income is not None:
        add(income < 0, "La rentabilidad sobre el capital es negativa en este periodo.", "Return on equity is negative for this period.")
        add(income >= 0, "La rentabilidad sobre el capital es positiva en este periodo.", "Return on equity is positive for this period.")
    combined = values.get("combined_ratio_reference")
    if combined is not None:
        add(combined > 1, "El índice combinado supera el 100%; los costos técnicos y operativos exceden la base de primas de referencia.", "The combined ratio exceeds 100%; technical and operating costs exceed the reference premium base.")
        add(combined <= 1, "El índice combinado no supera el 100% bajo la fórmula utilizada.", "The combined ratio does not exceed 100% under the formula used.")
    return notes


def render_dashboard(payload, lang, ratio_label, percent_ratios):
    es = lang == "es"
    ratios = payload.get("ratios", [])
    values = {r["name"]: r["value"] for r in ratios if isinstance(r.get("value"), (int, float)) and not isinstance(r.get("value"), bool)}
    data = payload.get("normalized_data", {})
    st.header("Panel de salud financiera" if es else "Financial health dashboard")
    st.caption("Lectura descriptiva del periodo, no una calificación crediticia ni una evaluación regulatoria." if es else "Descriptive period snapshot, not a credit rating or regulatory assessment.")

    cols = st.columns(4)
    for col, (key, spanish, english, percent) in zip(cols, KEY_METRICS):
        value = values.get(key)
        col.metric(spanish if es else english, _number(value, percent) if value is not None else "—")
    st.caption("— = sin datos suficientes para calcular el indicador." if es else "— = insufficient data to calculate this metric.")

    st.subheader("Lectura de resultados" if es else "What the results suggest")
    notes = _assessment(values, lang)
    if notes:
        for note in notes:
            st.markdown(f"- {note}")
    else:
        st.info("No hay indicadores clave suficientes para generar observaciones." if es else "Not enough key indicators to generate observations.")

    st.subheader("Explorador de indicadores" if es else "Ratio explorer")
    tabs = st.tabs([{"Liquidity": "Liquidez", "Solvency": "Solvencia", "Profitability": "Rentabilidad", "Underwriting": "Operación técnica"}[g] if es else g for g in GROUPS])
    for (group, keys), tab in zip(GROUPS.items(), tabs):
        with tab:
            rows = [{"Indicador" if es else "Indicator": ratio_label(k, lang), "Valor" if es else "Value": v, "Unidad" if es else "Unit": "%" if k in percent_ratios else "x"} for k in keys if (v := values.get(k)) is not None]
            if not rows:
                st.info("Sin indicadores calculables en esta categoría." if es else "No available ratios in this category.")
                continue
            frame = pd.DataFrame(rows)
            for unit in ["x", "%"]:
                subset = frame[frame["Unidad" if es else "Unit"] == unit].copy()
                if not subset.empty:
                    if unit == "%":
                        subset["Valor" if es else "Value"] *= 100
                    st.caption(("Porcentajes" if es else "Percentages") if unit == "%" else ("Múltiplos" if es else "Multiples"))
                    st.bar_chart(subset.set_index("Indicador" if es else "Indicator")[["Valor" if es else "Value"]], horizontal=True)
            st.dataframe(frame.assign(**{"Valor" if es else "Value": frame.apply(lambda r: _number(r["Valor" if es else "Value"], r["Unidad" if es else "Unit"] == "%"), axis=1)}), hide_index=True, use_container_width=True)

    assets, liabilities, equity = (data.get(k) for k in ("total_assets", "total_liabilities", "equity"))
    if all(isinstance(v, (int, float)) and v >= 0 for v in (assets, liabilities, equity)) and assets > 0:
        st.subheader("Estructura del balance" if es else "Balance sheet structure")
        st.bar_chart(pd.DataFrame({"Concepto" if es else "Concept": ["Pasivos" if es else "Liabilities", "Capital" if es else "Equity"], "Valor" if es else "Value": [liabilities, equity]}).set_index("Concepto" if es else "Concept"))
        if abs((liabilities + equity) - assets) > max(1, assets * 0.01):
            st.warning("El activo no coincide con pasivo más capital; revisa las cifras de origen." if es else "Assets do not reconcile to liabilities plus equity; review source figures.")

    available = len(values)
    st.caption((f"{available} indicadores calculados. La interpretación depende del contexto, la calidad de los datos y las normas aplicables; no se comparan periodos sin información histórica." if es else f"{available} ratios calculated. Interpretation depends on context, data quality and applicable standards; no period comparison is made without historical data."))


def render_category_dashboard(group, ratios, data, lang, ratio_label, format_value, percent_ratios, interpretations):
    """Show only the selected category and its relevant charts."""
    es = lang == "es"
    if not ratios:
        st.info("No hay ratios calculables en esta categoría." if es else "No calculable ratios in this category.")
        return
    values = {r["name"]: r["value"] for r in ratios if r.get("value") is not None}
    st.subheader("Indicadores" if es else "Indicators")
    cols = st.columns(min(3, len(ratios)))
    for idx, ratio in enumerate(ratios):
        with cols[idx % len(cols)]:
            st.metric(ratio_label(ratio["name"], lang), format_value(ratio["name"], ratio["value"], lang))
    rows = []
    for ratio in ratios:
        meaning = interpretations.get(ratio["name"], (ratio.get("interpretation", ""),) * 2)
        rows.append({"Indicador" if es else "Indicator": ratio_label(ratio["name"], lang),
                     "Resultado" if es else "Result": format_value(ratio["name"], ratio["value"], lang),
                     "Fórmula" if es else "Formula": ratio.get("formula", ""),
                     "Interpretación" if es else "Interpretation": meaning[0 if es else 1]})
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.subheader("Visualización" if es else "Visualization")
    for percent in (True, False):
        subset = [(ratio_label(k, lang), v * 100 if percent else v)
                  for k, v in values.items() if (k in percent_ratios) == percent]
        if subset:
            st.caption(("Porcentajes (%)" if es else "Percentages (%)") if percent else
                       ("Múltiplos (x)" if es else "Multiples (x)"))
            frame = pd.DataFrame(subset, columns=["Indicador", "Valor"]).set_index("Indicador")
            st.bar_chart(frame, horizontal=len(subset) > 2)
    if group == "Solvency":
        liabilities = data.get("total_liabilities")
        equity = data.get("total_equity", data.get("equity"))
        if liabilities is not None and equity is not None and liabilities >= 0 and equity >= 0 and liabilities + equity > 0:
            import plotly.express as px
            chart = pd.DataFrame({"Concept": ["Pasivos" if es else "Liabilities", "Capital" if es else "Equity"],
                                  "Amount": [liabilities, equity]})
            st.caption("Composición del financiamiento" if es else "Financing composition")
            st.plotly_chart(px.pie(chart, names="Concept", values="Amount", hole=0.45), use_container_width=True)
    if group == "Underwriting":
        earned = data.get("net_premiums_earned")
        claims = data.get("claims_incurred")
        acquisition = data.get("acquisition_costs")
        if earned is not None and claims is not None and acquisition is not None and earned > 0:
            breakdown = pd.DataFrame({"Component": ["Siniestros" if es else "Claims", "Adquisición" if es else "Acquisition"],
                                      "Amount": [claims, acquisition]})
            if (breakdown["Amount"] >= 0).all() and breakdown["Amount"].sum() > 0:
                import plotly.express as px
                st.caption("Distribución de costos técnicos identificados" if es else "Identified underwriting cost mix")
                st.plotly_chart(px.pie(breakdown, names="Component", values="Amount", hole=0.4), use_container_width=True)
    notes = _assessment(values, lang)
    if notes:
        st.subheader("Lectura de resultados" if es else "What the results suggest")
        for note in notes:
            st.write("• " + note)
    st.caption("Los ratios son descriptivos; no sustituyen la evaluación regulatoria de solvencia." if es else
               "These ratios are descriptive and do not replace regulatory solvency assessment.")
