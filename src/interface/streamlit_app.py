# Streamlit GUI: multi-year financial ratios, dashboard and sales projection for insurers
import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src.financial_engine.catalog import CATALOG, CATEGORIES
from src.interface import charts, theme, views
from src.interface.i18n import concept_label, tr
from src.interpretation.insights import build_insights
from src.orchestrator.multiyear import SUMMARY_KEYS, SUPPORTED, analyze, discover_files, extract_statements
from src.reporting.excel_export import build_workbook
from src.reporting.formatting import money, pct

st.set_page_config(page_title="Financial Ratios Insurance", page_icon="", layout="wide")


# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------
def show_chart(fig, key):
    st.plotly_chart(fig, key=key)


def show_table(df, **kwargs):
    """Full-width dataframe that works on old and new Streamlit versions."""
    try:
        st.dataframe(df, hide_index=True, width="stretch", **kwargs)
    except Exception:
        st.dataframe(df, hide_index=True, use_container_width=True, **kwargs)


def candidate_folders():
    """Folders under data/ that directly contain statement files."""
    root = PROJECT_ROOT / "data"
    found = []
    if root.exists():
        for folder in [root, *sorted(p for p in root.iterdir() if p.is_dir())]:
            if len(discover_files(folder)) >= 2:
                found.append(folder)
    return found


def run_extraction(paths, names=None):
    with st.spinner(TT("analyzing")):
        try:
            st.session_state["extraction"] = extract_statements(paths, names=names)
            st.session_state["overrides"] = {}
            st.session_state["editor_version"] = 0
            st.session_state["error"] = None
        except Exception as exc:  # surface the problem instead of a stack trace
            st.session_state["extraction"] = None
            st.session_state["error"] = str(exc)


def save_uploads(files):
    folder = Path(tempfile.mkdtemp(prefix="pia_"))
    paths, names = [], {}
    for uploaded in files:
        target = folder / Path(uploaded.name).name
        target.write_bytes(uploaded.getbuffer())
        paths.append(target)
        names[str(target)] = uploaded.name
    return paths, names


# ------------------------------------------------------------------------------------------------
# sidebar
# ------------------------------------------------------------------------------------------------
st.markdown(theme.CSS, unsafe_allow_html=True)
lang = st.sidebar.radio("Idioma / Language", ["es", "en"], format_func=lambda v: "Español" if v == "es" else "English", horizontal=True)
TT = tr(lang)
st.sidebar.markdown(f"###  {TT('app_title')}")
source = st.sidebar.radio(TT("source"), ["folder", "upload"], format_func=lambda v: TT("src_folder") if v == "folder" else TT("src_upload"))

if source == "folder":
    candidates = candidate_folders()
    default = str(candidates[-1] if candidates else PROJECT_ROOT / "data")
    folder_text = st.sidebar.text_input(TT("folder"), value=default)
    if st.sidebar.button(TT("analyze"), type="primary"):
        files = discover_files(folder_text) if Path(folder_text).is_dir() else []
        if files:
            run_extraction(files)
        else:
            st.sidebar.error(TT("no_folder"))
    # First visit: analyse the bundled data automatically so the dashboard is not empty.
    if "extraction" not in st.session_state and "autoran" not in st.session_state and candidates:
        st.session_state["autoran"] = True
        run_extraction(discover_files(candidates[-1]))
else:
    uploads = st.sidebar.file_uploader(TT("upload"), accept_multiple_files=True,
                                       type=[s.lstrip(".") for s in sorted(SUPPORTED)], help=TT("upload_help"))
    if st.sidebar.button(TT("analyze"), type="primary", disabled=not uploads):
        paths, names = save_uploads(uploads)
        run_extraction(paths, names)

st.sidebar.markdown(f'<p class="note">{TT("disclaimer")}</p>', unsafe_allow_html=True)

# ------------------------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------------------------
if st.session_state.get("error"):
    st.error(st.session_state["error"])
extraction = st.session_state.get("extraction")
if extraction is None or not extraction.years:
    st.markdown(f'<div class="hero"><h1>{TT("app_title")}</h1><p>{TT("start")}</p></div>', unsafe_allow_html=True)
    if extraction is not None:
        for issue in extraction.issues:
            st.warning(issue["message"])
    st.stop()

overrides = st.session_state.get("overrides", {})
analysis = analyze(extraction, overrides)
years = analysis.years

st.markdown(views.hero_html(analysis, lang, TT("app_title")), unsafe_allow_html=True)
tab_summary, tab_ratios, tab_projection, tab_data, tab_export = st.tabs(
    [TT("tab_summary"), TT("tab_ratios"), TT("tab_projection"), TT("tab_data"), TT("tab_export")])

# ---------------------------------------------------------------- Summary
with tab_summary:
    c1, c2, _ = st.columns([1, 1, 3])
    year = c1.selectbox(TT("kpi_year"), years, index=len(years) - 1, key="kpi_year")
    others = [y for y in years if y != year] or years
    default_cmp = max([y for y in others if y < year], default=others[0])
    compare = c2.selectbox(TT("kpi_compare"), others, index=others.index(default_cmp), key="kpi_compare")

    cards = views.kpi_cards(analysis, year, compare, lang)
    for start in (0, 4):
        cols = st.columns(4)
        for col, card in zip(cols, cards[start:start + 4]):
            col.markdown(views.kpi_html(card, TT("vs")), unsafe_allow_html=True)
        st.write("")

    extra = views.supplementary(analysis, year, TT)
    if extra:
        st.markdown(f'<div class="section-title">{TT("supplementary")}</div>', unsafe_allow_html=True)
        cols = st.columns(len(extra))
        for col, (label, value) in zip(cols, extra):
            col.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value">{value}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<p class="note">{TT("supp_note")}</p>', unsafe_allow_html=True)

    st.markdown(f'<div class="section-title">{TT("insights")}</div>', unsafe_allow_html=True)
    for item in build_insights(analysis):
        st.markdown(views.insight_html(item, lang), unsafe_allow_html=True)

    st.markdown(f'<div class="section-title">{TT("charts")}</div>', unsafe_allow_html=True)
    left, right = st.columns(2)
    with left:
        show_chart(charts.premiums_and_income(analysis, TT), "ch_prem")
    with right:
        if views.bridge_data(analysis, year, TT):
            show_chart(charts.profit_bridge(analysis, year, TT), "ch_bridge")
    left, right = st.columns(2)
    with left:
        show_chart(charts.ratio_lines(analysis, ("return_on_equity", "return_on_assets", "net_margin_written_premiums", "technical_margin"),
                                      TT("ch_ratios"), TT, lang), "ch_prof")
    with right:
        show_chart(charts.ratio_lines(analysis, ("claims_ratio", "acquisition_cost_ratio"), TT("ch_costs"), TT, lang), "ch_cost")
    if views.balance_composition(analysis):
        show_chart(charts.balance_stack(analysis, TT), "ch_bal")

# ---------------------------------------------------------------- Ratios
with tab_ratios:
    st.markdown(f"### {TT('ratios_title')}")
    c1, c2, c3 = st.columns([1, 1, 1])
    cat_choice = c1.selectbox(TT("category"), [None, *CATEGORIES], format_func=lambda v: TT("all") if v is None else views.category_label(v, lang))
    r_year = c2.selectbox(TT("kpi_year"), years, index=len(years) - 1, key="ratio_year")
    st.markdown(views.ratio_table_html(analysis, r_year, None, lang, cat_choice), unsafe_allow_html=True)

    st.markdown(f'<div class="section-title">{TT("detail")}</div>', unsafe_allow_html=True)
    pool = [s for s in CATALOG if cat_choice in (None, s.category)]
    spec = st.selectbox(TT("indicator"), pool, format_func=lambda s: views.label_of(s, lang))
    left, right = st.columns([2, 1])
    with left:
        show_chart(charts.indicator_trend(analysis, spec.code, lang, r_year), "ch_ind")
    with right:
        st.markdown(f"**{TT('meaning')}**")
        st.write(spec.meaning_es if lang == "es" else spec.meaning_en)
        st.markdown(f"**{TT('category')}:** {views.category_label(spec.category, lang)}")

# ---------------------------------------------------------------- Projection
with tab_projection:
    st.markdown(f"### {TT('projection_title')}")
    sub_sales, sub_claims = st.tabs([TT("sales"), TT("claims")])
    for sub, proj, scenarios, color, tag in ((sub_sales, analysis.sales, analysis.sales_scenarios, theme.TEAL, "s"),
                                             (sub_claims, analysis.claims, analysis.claims_scenarios, theme.RED, "c")):
        with sub:
            if proj is None:
                st.info("—")
                continue
            kp = [
                (f"{TT('proj_total')} {proj.horizon_year}", money(proj.total, lang), pct(proj.total_growth, 1, True) + f" {TT('proj_growth')}"),
                (TT("proj_mean"), pct(proj.mean_growth, 2, True), ""),
                (TT("proj_monthly"), pct(proj.monthly_rate, 3, True), ""),
                (TT("proj_base"), money(proj.monthly_base, lang), ""),
            ]
            for col, (label, value, sub_text) in zip(st.columns(4), kp):
                col.markdown(f'<div class="kpi"><div class="label">{label}</div><div class="value" style="font-size:1.45rem">{value}</div>'
                             f'<div class="delta neutral">{sub_text}</div></div>', unsafe_allow_html=True)
            st.write("")
            left, right = st.columns(2)
            with left:
                show_chart(charts.projection_annual(proj, scenarios, TT, color), f"pa_{tag}")
            with right:
                show_chart(charts.projection_monthly(proj, TT, color), f"pm_{tag}")
            st.markdown(f'<div class="section-title">{TT("proj_scenarios")}</div>', unsafe_allow_html=True)
            show_table(pd.DataFrame([{TT("method"): s.name, f"{TT('proj_total')} {proj.horizon_year}": money(s.total, lang),
                                      TT("growth"): pct(s.growth, 2, True), TT("description"): s.description} for s in scenarios]))
            with st.expander(TT("proj_monthly_table")):
                show_table(pd.DataFrame([{TT("month"): m.month, TT("value"): f"{m.value:,.2f}", TT("rate"): pct(m.rate, 4),
                                          TT("cum"): pct(m.cumulative_vs_base, 2, True)} for m in proj.months]))
            with st.expander(TT("proj_method")):
                st.write(TT("proj_method_text"))
                st.caption(TT("proj_caveat"))

# ---------------------------------------------------------------- Data & validation
with tab_data:
    st.markdown(f"### {TT('data_title')}")
    st.markdown(f'<div class="section-title">{TT("files")}</div>', unsafe_allow_html=True)
    show_table(pd.DataFrame([{TT("year"): f["year"], TT("type"): TT(f["kind"]), TT("file"): f["name"],
                              TT("detected_by"): TT("header") if f["source"] == "header" else TT("filename")}
                             for f in sorted(extraction.files, key=lambda f: (f["year"], f["kind"]))]))

    st.markdown(f'<div class="section-title">{TT("checks")}</div>', unsafe_allow_html=True)
    if analysis.checks:
        frame = pd.DataFrame([{TT("year"): c["year"], TT("check"): c["check"], TT("expected"): f"{c['expected']:,.2f}",
                               TT("reported"): f"{c['actual']:,.2f}", TT("diff"): f"{c['difference']:,.2f}", TT("status"): c["status"]}
                              for c in analysis.checks])
        show_table(frame)
    st.markdown(f'<div class="section-title">{TT("issues")}</div>', unsafe_allow_html=True)
    notices = [i for i in analysis.issues if i.get("severity") != "info"]
    if notices:
        for issue in notices:
            st.warning(issue["message"])
    else:
        st.success(TT("no_issues"))
    for proxy in analysis.proxies[:1]:
        st.caption(f"{TT('proxy_note')}: {proxy['note']}")

    st.markdown(f'<div class="section-title">{TT("edit_title")}</div>', unsafe_allow_html=True)
    st.caption(TT("edit_help"))
    version = st.session_state.get("editor_version", 0)
    original = views.amounts_frame(analysis, lang, SUMMARY_KEYS, lambda k: TT(k) if k == "concept" else concept_label(k, lang))
    concept_col = TT("concept")
    edited = st.data_editor(
        original, hide_index=True, key=f"editor_{version}", disabled=["key", concept_col],
        column_config={"key": None, **{str(y): st.column_config.NumberColumn(str(y), format="%.2f") for y in years}})
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button(TT("apply")):
        new = views.overrides_from_edit(original, edited, years)
        if new:
            st.session_state["overrides"] = views.merge_overrides(overrides, new)
            st.session_state["editor_version"] = version + 1
            st.rerun()
    if b2.button(TT("reset"), disabled=not overrides):
        st.session_state["overrides"] = {}
        st.session_state["editor_version"] = version + 1
        st.rerun()
    if overrides:
        st.info(TT("applied") + " " + json.dumps({str(y): list(v) for y, v in overrides.items()}, ensure_ascii=False))

    for table, key in ((extraction.income, "full_er"), (extraction.balance, "full_bg")):
        with st.expander(TT(key)):
            rows = [{TT("concept"): r.label, **{str(y): r.values.get(y) for y in table.years}, "key": r.key or ""} for r in table.rows]
            show_table(pd.DataFrame(rows))

# ---------------------------------------------------------------- Export
with tab_export:
    st.markdown(f"### {TT('export_title')}")
    st.caption(TT("dl_excel_help"))
    xlsx = build_workbook(analysis)
    st.download_button(TT("dl_excel"), data=xlsx, file_name=f"analisis_financiero_{years[0]}_{years[-1]}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary")
    ratios_csv = views.ratios_frame(analysis, lang).to_csv(index=False).encode("utf-8-sig")
    st.download_button(TT("dl_csv"), data=ratios_csv, file_name="razones_financieras.csv", mime="text/csv")
    st.download_button(TT("dl_json"), data=json.dumps(analysis.to_dict(), ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                       file_name="resultado_analisis.json", mime="application/json")
