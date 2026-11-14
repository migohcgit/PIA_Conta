#Streamlit GUI for the Financial Ratios Insurance modular backend
import json
import hashlib
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src.orchestrator.statements import analyze_statements, _extract, INCOME_KEYS, calculate_from_data
from src.interface.dashboard_view import render_category_dashboard, GROUPS
from src.interface.review_tools import rows_for_review, reviewed_values, reconcile, CANONICAL_KEYS

TEXT = {
    "es": {
        "title": "Financial Ratios Insurance", "subtitle": "Análisis de estados financieros para aseguradoras",
        "instructions": "Carga el balance general y el estado de resultados. El motor combinará ambos documentos antes de calcular las razones.",
        "balance": "Balance general", "income": "Estado de resultados", "run": "Analizar estados financieros",
        "period": "Periodo del informe", "language": "Idioma", "results": "Resultados", "concepts": "Conceptos reconocidos",
        "ratios": "Razones financieras", "warnings": "Validación y advertencias", "formula": "Fórmula", "value": "Resultado",
        "status": "Estado", "download_json": "Descargar resultado JSON", "download_csv": "Descargar razones CSV",
        "upload_help": "Formatos permitidos: PDF, XLSX, XLS, XLSM y CSV.", "no_result": "Carga ambos estados y pulsa Analizar para comenzar.",
        "calculated": "Calculada", "missing": "No calculable con los datos disponibles", "source_data": "Datos normalizados",
        "no_warnings": "No se generaron advertencias de validación.", "files_missing": "Debes cargar ambos archivos para analizar.",
        "analysis_error": "No se pudo completar el análisis. Revisa los archivos y las advertencias.", "company": "Aseguradora / entidad (opcional)",
        "filter": "Filtrar razones", "all": "Todas", "calculated_only": "Solo calculables", "missing_only": "Solo no calculables",
        "notes": "Notas", "status_ok": "Proceso terminado", "ratio_groups": "Categorías",
    },
    "en": {
        "title": "Financial Ratios Insurance", "subtitle": "Financial statement analysis for insurers",
        "instructions": "Upload the balance sheet and income statement. The engine combines both documents before calculating ratios.",
        "balance": "Balance sheet", "income": "Income statement", "run": "Analyze financial statements",
        "period": "Reporting period", "language": "Language", "results": "Results", "concepts": "Recognized concepts",
        "ratios": "Financial ratios", "warnings": "Validation and warnings", "formula": "Formula", "value": "Result",
        "status": "Status", "download_json": "Download JSON result", "download_csv": "Download ratios CSV",
        "upload_help": "Supported formats: PDF, XLSX, XLS, XLSM and CSV.", "no_result": "Upload both statements and click Analyze to begin.",
        "calculated": "Calculated", "missing": "Not calculable with available data", "source_data": "Normalized data",
        "no_warnings": "No validation warnings were generated.", "files_missing": "Upload both files to analyze.",
        "analysis_error": "The analysis could not be completed. Review the files and warnings.", "company": "Insurer / entity (optional)",
        "filter": "Filter ratios", "all": "All", "calculated_only": "Calculable only", "missing_only": "Not calculable only",
        "notes": "Notes", "status_ok": "Process completed", "ratio_groups": "Categories",
    }
}

RATIO_LABELS = {
    "current_ratio": ("Razón circulante", "Current ratio"),
    "cash_ratio": ("Razón de efectivo", "Cash ratio"),
    "debt_to_assets": ("Pasivo / Activo", "Liabilities / assets"),
    "equity_ratio": ("Capital / Activo", "Equity ratio"),
    "net_profit_margin": ("Margen neto", "Net profit margin"),
    "investment_yield": ("Rendimiento de inversiones", "Investment yield"),
    "liquidity_current": ("Activo circulante / Pasivo circulante", "Current assets / Current liabilities"),
    "liquidity_available_to_exigible": ("Activo disponible / Pasivo exigible", "Available assets / Exigible liabilities"),
    "liquidity_current_to_exigible": ("Activo circulante / Pasivo exigible", "Current assets / Exigible liabilities"),
    "liquidity_current_to_technical_reserves": ("Activo circulante / Reservas técnicas", "Current assets / Technical reserves"),
    "liquidity_investments_to_current_liabilities": ("Inversiones financieras / Pasivo circulante", "Financial investments / Current liabilities"),
    "solvency_total_assets_to_liabilities": ("Solvencia total", "Total solvency"),
    "solvency_capital_to_gross_requirement": ("Capital y reservas preventivas / Requerimiento bruto de solvencia", "Equity and preventive reserves / Gross solvency requirement"),
    "guarantee_capital_coverage": ("Capital de garantía / Capital mínimo de garantía", "Guarantee capital / Minimum guarantee capital"),
    "solvency_margin_to_guarantee_capital": ("Margen de solvencia / Capital de garantía", "Solvency margin / Guarantee capital"),
    "preventive_reserves_to_claims": ("Reservas preventivas / Siniestros y recuperaciones", "Preventive reserves / Claims and recoveries"),
    "investment_backing_contractual_obligations": ("Respaldo de inversiones a obligaciones contractuales", "Investment backing for contractual obligations"),
    "real_growth_capital_reserves": ("Crecimiento real de reservas y capital", "Real growth in reserves and equity"),
    "reinsurance_recovery_ratio": ("Recuperaciones y comisiones / Prima cedida", "Recoveries and commissions / Ceded premiums"),
    "reinsurer_profit_ratio": ("Resultado del reaseguro", "Reinsurance result"),
    "adjusted_roa": ("ROA ajustado", "Adjusted ROA"),
    "adjusted_roe": ("ROE ajustado", "Adjusted ROE"),
    "adjusted_return_on_written_premiums": ("Rentabilidad ajustada / Prima emitida", "Adjusted return / Written premiums"),
    "solvency_adjusted_assets": ("Solvencia ajustada", "Adjusted solvency"),
    "solvency_retained_premiums_to_equity": ("Primas retenidas / Capital contable", "Retained premiums / Equity"),
    "leverage_liabilities_to_equity": ("Pasivo total / Capital contable", "Total liabilities / Equity"),
    "leverage_technical_reserves_to_equity": ("Reservas técnicas / Capital contable", "Technical reserves / Equity"),
    "leverage_reserve_change_to_equity": ("Cambio de reservas / Capital contable", "Reserve change / Equity"),
    "operating_cost_ratio": ("Costo medio de operación", "Operating cost ratio"),
    "acquisition_cost_ratio": ("Costo medio de adquisición", "Acquisition cost ratio"),
    "claims_ratio": ("Costo medio de siniestralidad", "Claims cost ratio"),
    "combined_ratio_reference": ("Índice combinado (referencia)", "Combined ratio (reference)"),
    "premium_adequacy": ("Suficiencia de prima", "Premium adequacy"),
    "premium_adequacy_with_financial_result": ("Suficiencia con resultado financiero", "Adequacy including financial result"),
    "ceded_premium_ratio": ("Prima cedida / Prima emitida", "Ceded / Written premiums"),
    "retention_ratio": ("Prima retenida / Prima emitida", "Retained / Written premiums"),
    "ceded_reinsurance_commission_ratio": ("Comisiones de reaseguro cedido / Prima cedida", "Ceded reinsurance commission ratio"),
    "excess_loss_cover_ratio": ("Cobertura de exceso de pérdida / Prima retenida", "Excess-of-loss cover ratio"),
    "nonproportional_recovery_ratio": ("Recuperación de siniestros no proporcional", "Non-proportional recovery ratio"),
    "retained_claims_ratio": ("Siniestros retenidos / Prima devengada de retención", "Retained claims / Earned retained premiums"),
    "retained_claims_ratio": ("Siniestralidad retenida / Prima devengada", "Retained claims ratio"),
    "return_on_equity": ("Utilidad neta / Capital contable", "Net income / Equity"),
    "return_on_paid_capital": ("Utilidad neta / Capital pagado", "Net income / Paid-in capital"),
    "return_on_paid_capital_plus_reserve": ("Utilidad neta / Capital pagado + Reserva", "Net income / Paid-in capital + reserve"),
    "net_margin_direct_premiums": ("Utilidad neta / Prima directa", "Net income / Direct premiums"),
    "net_margin_written_premiums": ("Utilidad neta / Prima emitida", "Net income / Written premiums"),
    "net_margin_retained_premiums": ("Utilidad neta / Prima retenida", "Net income / Retained premiums"),
    "technical_margin": ("Utilidad técnica / Prima devengada", "Technical result / Earned premiums"),
    "net_income_to_working_capital": ("Utilidad neta / Capital de trabajo", "Net income / Working capital"),
    "return_on_assets": ("ROA: Utilidad neta / Activo total", "ROA: Net income / Total assets"),
    "return_on_equity_reference": ("ROE: Utilidad neta / Capital contable", "ROE: Net income / Equity"),
    "net_income_to_written_premiums": ("Utilidad neta / Prima emitida (referencia)", "Net income / Written premiums (reference)"),
}

RATIO_INTERPRETATIONS = {
    "liquidity_current": ("Muestra cuántas veces el activo circulante puede cubrir el pasivo circulante.", "Shows how many times current assets cover current liabilities."),
    "liquidity_available_to_exigible": ("Aproxima la capacidad de cubrir obligaciones exigibles mediante efectivo y equivalentes; no incluye otros activos líquidos no identificados.", "Approximates the ability to cover exigible liabilities with cash and equivalents; other liquid assets are not identified."),
    "liquidity_current_to_exigible": ("Combina la capacidad del activo circulante frente a las obligaciones exigibles.", "Combines current-asset coverage of exigible liabilities."),
    "liquidity_current_to_technical_reserves": ("Indica la capacidad de respuesta frente a obligaciones técnicas con asegurados mediante activos circulantes.", "Indicates current-asset coverage of technical obligations to policyholders."),
    "liquidity_investments_to_current_liabilities": ("Mide cuántas veces las inversiones financieras respaldan las obligaciones de corto plazo.", "Measures how many times financial investments cover short-term liabilities."),
    "solvency_total_assets_to_liabilities": ("Indica cuántas veces los activos totales cubren el pasivo total.", "Indicates how many times total assets cover total liabilities."),
    "solvency_adjusted_assets": ("Mide la cobertura de obligaciones de acreedores distintos de los asegurados; requiere clasificaciones regulatorias completas.", "Measures coverage of creditors other than policyholders; full regulatory classifications are required."),
    "operating_cost_ratio": ("Muestra la proporción de primas destinada a cubrir costos de operación. En este caso, primas emitidas se usan como aproximación de prima directa.", "Shows the share of premiums used to cover operating costs. Written premiums are used as a proxy for direct premiums here."),
    "acquisition_cost_ratio": ("Muestra la proporción de primas retenidas destinada a costos netos de adquisición.", "Shows the share of retained premiums used for net acquisition costs."),
    "claims_ratio": ("Indica la proporción de primas devengadas destinada al costo neto de siniestralidad.", "Shows the share of earned premiums absorbed by net claims costs."),
    "combined_ratio_reference": ("Suma los costos medios de operación, adquisición y siniestralidad según las fórmulas de la referencia adjunta.", "Adds operating, acquisition and claims cost ratios as specified in the supplied reference."),
    "premium_adequacy": ("Un valor negativo indica insuficiencia de prima bajo la definición de la referencia adjunta.", "A negative value indicates premium inadequacy under the supplied reference definition."),
    "premium_adequacy_with_financial_result": ("Representa la suficiencia de prima incluyendo el resultado financiero.", "Represents premium adequacy including the financial result."),
    "ceded_premium_ratio": ("Muestra la proporción de primas emitidas cedida al reaseguro.", "Shows the share of written premiums ceded to reinsurers."),
    "retention_ratio": ("Refleja el porcentaje de primas emitidas que la compañía retiene.", "Shows the percentage of written premiums retained by the company."),
    "ceded_reinsurance_commission_ratio": ("Indica la proporción de primas cedidas asociada a comisiones de reaseguro cedido.", "Shows ceded reinsurance commissions relative to ceded premiums."),
    "excess_loss_cover_ratio": ("Mide el costo de la cobertura de exceso de pérdida respecto a primas retenidas.", "Measures excess-of-loss cover cost relative to retained premiums."),
    "return_on_equity": ("Muestra cuánto resultado neto produjo la operación por cada peso de capital contable.", "Shows net income generated for each unit of equity."),
    "return_on_paid_capital": ("Mide la rentabilidad de las aportaciones de capital pagado por los accionistas.", "Measures the return on shareholder paid-in capital."),
    "return_on_paid_capital_plus_reserve": ("Mide la rentabilidad del capital pagado junto con las reservas de capital identificadas.", "Measures returns on paid-in capital plus identified capital reserves."),
    "net_margin_direct_premiums": ("Muestra la utilidad neta en proporción a la prima directa; se usa prima emitida como aproximación cuando no está separada.", "Shows net income relative to direct premiums; written premiums are used as a proxy when not separately disclosed."),
    "net_income_to_working_capital": ("Muestra la utilidad neta respecto al capital de trabajo; requiere clasificar activos y pasivos circulantes.", "Shows net income relative to working capital; current assets and liabilities must be classified."),
    "return_on_paid_capital": ("Mide la rentabilidad del capital pagado por los accionistas.", "Measures the return on paid-in shareholder capital."),
    "net_margin_written_premiums": ("Muestra la utilidad neta como proporción de las primas emitidas.", "Shows net income as a share of written premiums."),
    "net_margin_retained_premiums": ("Muestra la utilidad neta como proporción de las primas retenidas.", "Shows net income as a share of retained premiums."),
    "technical_margin": ("Mide la rentabilidad del resultado técnico respecto a las primas de retención devengadas.", "Measures technical profitability relative to earned retained premiums."),
    "return_on_assets": ("Mide el rendimiento del activo total usando saldos al cierre; el promedio del periodo es preferible.", "Measures return on total assets using period-end balances; period averages are preferable."),
    "adjusted_roa": ("Mide el rendimiento de activos ajustando la utilidad por cambios de superávit y reservas de capital; requiere esos movimientos.", "Measures asset returns adjusted for changes in surplus and capital reserves; those movements are required."),
    "adjusted_roe": ("Mide el rendimiento del capital ajustando la utilidad por cambios de superávit y reservas de capital; requiere esos movimientos.", "Measures equity returns adjusted for changes in surplus and capital reserves; those movements are required."),
}

PERCENT_RATIOS = {name for name in RATIO_LABELS if any(part in name for part in (
    "cost_ratio", "claims_ratio", "combined_ratio", "adequacy", "premium_ratio", "retention_ratio",
    "commission_ratio", "margin", "return_on", "net_income_to_written", "net_income_to_working", "equity_ratio",
    "debt_to_assets", "investment_yield", "excess_loss_cover_ratio", "solvency_retained_premiums_to_equity",
    "reinsurance_recovery_ratio", "reinsurer_profit_ratio", "preventive_reserves_to_claims"))}


def _ratio_label(name, lang):
    labels = RATIO_LABELS.get(name)
    if labels:
        return labels[0 if lang == "es" else 1]
    return name.replace("_", " ").title()


def _format_value(name, value, lang):
    if value is None:
        return "No calculable" if lang == "es" else "Not calculable"
    if name in PERCENT_RATIOS:
        return f"{value * 100:,.2f}%"
    return f"{value:,.3f}x"


def _stage_files(balance_file, income_file):
    with tempfile.TemporaryDirectory(prefix="financial-ratios-") as tmp:
        bpath = Path(tmp) / Path(balance_file.name).name
        ipath = Path(tmp) / Path(income_file.name).name
        bpath.write_bytes(balance_file.getvalue())
        ipath.write_bytes(income_file.getvalue())
        braw, balance, bdupes, bunknown = _extract(bpath)
        iraw, income, idupes, iunknown = _extract(ipath)
    return balance, income, bdupes + idupes, bunknown + iunknown, braw, iraw


def _editor(data, label, key):
    st.subheader(label)
    rows = [{"Concepto / Concept": k, "Valor / Value": float(v)} for k, v in sorted(data.items())]
    edited = st.data_editor(
        pd.DataFrame(rows), key=key, hide_index=True, use_container_width=True,
        num_rows="dynamic", column_config={
            "Concepto / Concept": st.column_config.TextColumn(required=True),
            "Valor / Value": st.column_config.NumberColumn(format="%.2f", required=True),
        },
    )
    result = {}
    for _, row in edited.iterrows():
        name = str(row["Concepto / Concept"]).strip()
        value = row["Valor / Value"]
        if not name or pd.isna(value):
            continue
        if name in result:
            raise ValueError(f"Duplicate concept: {name}")
        result[name] = float(value)
    return result


def run_app():
    st.set_page_config(page_title="Financial Ratios Insurance", page_icon="📊", layout="wide")
    with st.sidebar:
        lang_choice = st.selectbox("Idioma / Language", ["Español", "English"])
        lang = "es" if lang_choice == "Español" else "en"
        t = TEXT[lang]
        st.markdown("### Financial Ratios Insurance")
        st.caption("Modular backend · PDF / Excel / CSV · ES / EN")
        period = st.text_input(t["period"], "FY2025")
        entity = st.text_input(t["company"], "Seguros Monterrey New York Life")
    es = lang == "es"
    st.title(t["title"])
    st.subheader(t["subtitle"])
    st.caption(("1. Cargar → 2. Revisar y editar → 3. Calcular y explorar" if es else
                "1. Upload → 2. Review and edit → 3. Calculate and explore"))

    if "workflow_stage" not in st.session_state:
        st.session_state.workflow_stage = "upload"
    if st.session_state.workflow_stage != "results":
        st.write("Carga ambos estados para revisar los conceptos antes del cálculo." if es else
                 "Upload both statements to review the extracted concepts before calculation.")
        left, right = st.columns(2)
        with left:
            balance_file = st.file_uploader(t["balance"], type=["pdf", "xlsx", "xls", "xlsm", "csv"], key="balance")
        with right:
            income_file = st.file_uploader(t["income"], type=["pdf", "xlsx", "xls", "xlsm", "csv"], key="income")
        if balance_file and income_file:
            fingerprint = (balance_file.name, hashlib.sha256(balance_file.getvalue()).hexdigest(), income_file.name, hashlib.sha256(income_file.getvalue()).hexdigest())
            if st.session_state.get("file_fingerprint") != fingerprint:
                st.session_state.file_fingerprint = fingerprint
                st.session_state.workflow_stage = "upload"
                st.session_state.pop("balance_editor", None)
                st.session_state.pop("income_editor", None)
                st.session_state.pop("balance_raw_editor", None)
                st.session_state.pop("income_raw_editor", None)
            if st.session_state.workflow_stage == "upload":
                if st.button("Extraer y revisar datos" if es else "Extract and review data", type="primary"):
                    try:
                        with st.spinner("Extrayendo datos…" if es else "Extracting data…"):
                            balance, income, duplicates, unknown, braw, iraw = _stage_files(balance_file, income_file)
                        st.session_state.balance_raw = rows_for_review(braw)
                        st.session_state.income_raw = rows_for_review(iraw)
                        st.session_state.extracted_balance = balance
                        st.session_state.extracted_income = income
                        st.session_state.extraction_duplicates = duplicates
                        st.session_state.extraction_unknown = unknown
                        st.session_state.workflow_stage = "review"
                        st.rerun()
                    except Exception as exc:
                        st.error(f"{t['analysis_error']} ({exc})")
        if st.session_state.workflow_stage != "review":
            return
        st.divider()
        st.header("Revisar y corregir datos" if es else "Review and correct data")
        st.info("Revisa todas las filas extraídas. Activa Include y asigna una Canonical key para utilizar una partida en los ratios. Las filas sin correspondencia se conservan para revisión." if es else
                "Review all extracted rows. Enable Include and assign a Canonical key to use a line in the ratios. Unmapped rows remain visible for review.")
        if st.session_state.extraction_duplicates:
            st.warning("Se encontraron conceptos duplicados. Resuélvelos antes de calcular." if es else
                       "Duplicate concepts were detected. Resolve them before calculation.")
        with st.form("review_form"):
            bcol, icol = st.columns(2)
            edited_frames = []
            for col, name, state_key, widget_key in [
                (bcol, t["balance"], "balance_raw", "balance_raw_editor"),
                (icol, t["income"], "income_raw", "income_raw_editor")]:
                with col:
                    st.subheader(name)
                    frame = st.data_editor(
                        st.session_state[state_key], key=widget_key, hide_index=True,
                        use_container_width=True, num_rows="dynamic",
                        column_config={
                            "Source label": st.column_config.TextColumn("Source label"),
                            "Amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                            "Canonical key": st.column_config.SelectboxColumn("Canonical key", options=[""] + CANONICAL_KEYS),
                            "Location": st.column_config.TextColumn("Location", disabled=True),
                            "Include": st.column_config.CheckboxColumn("Include"),
                        })
                    edited_frames.append(frame)
                    st.caption((f"{len(frame)} filas extraídas · {sum(frame['Include'].fillna(False))} seleccionadas" if es else
                                f"{len(frame)} extracted rows · {sum(frame['Include'].fillna(False))} selected"))
            submitted = st.form_submit_button("Calcular ratios" if es else "Calculate ratios", type="primary", use_container_width=True)
        balance_frame, income_frame = edited_frames
        st.download_button("Descargar revisión CSV" if es else "Download review CSV",
                           pd.concat([balance_frame.assign(Statement="Balance"), income_frame.assign(Statement="Income")]).to_csv(index=False).encode("utf-8-sig"),
                           file_name="financial-review.csv", mime="text/csv")
        if submitted:
            try:
                balance = reviewed_values(balance_frame)
                income = reviewed_values(income_frame)
                conflicts = set(balance) & set(income) - INCOME_KEYS
                if conflicts:
                    raise ValueError("Keys assigned in both statements: " + ", ".join(sorted(conflicts)))
                merged = dict(balance)
                merged.update({k: v for k, v in income.items() if k in INCOME_KEYS or k not in merged})
                st.session_state.reconciliation = reconcile(merged)
                payload = calculate_from_data(merged).to_dict()
                payload["metadata"].update({"period": period, "entity": entity,
                    "balance_sheet_file": balance_file.name, "income_statement_file": income_file.name,
                    "edited_before_calculation": True})
                st.session_state.analysis_payload = payload
                st.session_state.workflow_stage = "results"
                st.rerun()
            except Exception as exc:
                st.error(f"{t['analysis_error']} ({exc})")
        return

    payload = st.session_state.analysis_payload
    top_left, top_right = st.columns([4, 1])
    with top_left:
        st.header(t["results"])
    with top_right:
        if st.button("← Editar datos" if es else "← Edit data"):
            st.session_state.workflow_stage = "review"
            st.rerun()
    ratios = payload.get("ratios", [])
    m1, m2, m3 = st.columns(3)
    m1.metric(t["concepts"], len(payload.get("normalized_data", {})))
    m2.metric(t["calculated"], sum(r.get("value") is not None for r in ratios))
    m3.metric(t["status"], payload.get("status", "—").upper())
    labels = {"Liquidity": ("Liquidez", "Liquidity"), "Solvency": ("Solvencia", "Solvency"),
              "Profitability": ("Rentabilidad", "Profitability"), "Underwriting": ("Operación técnica", "Underwriting"),
              "Other": ("Otros", "Other")}
    known = set().union(*[set(keys) for keys in GROUPS.values()])
    groups = dict(GROUPS)
    others = [r["name"] for r in ratios if r["name"] not in known]
    if others:
        groups["Other"] = others
    tabs = st.tabs([labels[g][0 if es else 1] for g in groups])
    for (group, keys), tab in zip(groups.items(), tabs):
        with tab:
            selected = [r for r in ratios if r["name"] in keys]
            render_category_dashboard(group, selected, payload.get("normalized_data", {}), lang, _ratio_label, _format_value, PERCENT_RATIOS, RATIO_INTERPRETATIONS)
    checks = st.session_state.get("reconciliation", [])
    if checks:
        with st.expander("Conciliación contable" if es else "Accounting reconciliation", expanded=True):
            st.dataframe(pd.DataFrame(checks), hide_index=True, use_container_width=True)
            if any(check["Status"] != "OK" for check in checks):
                st.warning("Hay diferencias contables que requieren revisión." if es else "Some accounting differences require review.")
    with st.expander(t["source_data"]):
        st.dataframe(pd.DataFrame([{"Concepto": k, "Valor (MXN)": v} for k, v in sorted(payload.get("normalized_data", {}).items())]),
                     hide_index=True, use_container_width=True)
    with st.expander(t["warnings"]):
        for issue in payload.get("issues", []):
            st.warning(issue.get("message", ""))
    st.download_button(t["download_json"], json.dumps(payload, ensure_ascii=False, indent=2),
                       file_name="financial-ratios-result.json", mime="application/json")
    st.download_button(t["download_csv"], pd.DataFrame(ratios).to_csv(index=False).encode("utf-8-sig"),
                       file_name="financial-ratios.csv", mime="text/csv")


if __name__ == "__main__":
    run_app()
