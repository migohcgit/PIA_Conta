"""Plotly figure builders. Each function returns a ``plotly.graph_objects.Figure``."""
import plotly.graph_objects as go

from src.interface import theme
from src.interface.views import balance_composition, bridge_data, label_of
from src.reporting.formatting import money_short


def _base(fig, title=None, height=340, legend=True):
    fig.update_layout(**{k: v for k, v in theme.plotly_layout(title, height, legend).items() if v is not None})
    fig.update_xaxes(showgrid=False, type="category", linecolor="#D9DFE8")
    fig.update_yaxes(gridcolor="#E9EEF4", zeroline=True, zerolinecolor="#C9D1DD")
    return fig


def premiums_and_income(analysis, t):
    years = [str(y) for y in analysis.years]
    prem = [analysis.summary[y].get("gross_premiums_written") for y in analysis.years]
    net = [analysis.summary[y].get("net_income") for y in analysis.years]
    fig = go.Figure()
    fig.add_bar(x=years, y=[None if v is None else v / 1e9 for v in prem], name=t("ch_premiums"), marker_color=theme.NAVY,
                text=[money_short(v) for v in prem], textposition="outside")
    fig.add_scatter(x=years, y=[None if v is None else v / 1e9 for v in net], name=t("ch_income"), mode="lines+markers",
                    line={"color": theme.AMBER, "width": 3}, marker={"size": 9}, yaxis="y2")
    fig = _base(fig, t("ch_premium_income"))
    fig.update_layout(yaxis={"rangemode": "tozero"},
                      yaxis2={"overlaying": "y", "side": "right", "showgrid": False, "rangemode": "tozero"})
    return fig


def profit_bridge(analysis, year, t):
    steps = bridge_data(analysis, year, t)
    fig = go.Figure(go.Waterfall(
        x=[s[0] for s in steps], y=[s[1] / 1e9 for s in steps], measure=[s[2] for s in steps],
        text=[f"{s[1] / 1e9:,.2f}" for s in steps], textposition="outside",
        increasing={"marker": {"color": theme.TEAL}}, decreasing={"marker": {"color": theme.RED}},
        totals={"marker": {"color": theme.NAVY}}, connector={"line": {"color": "#C9D1DD"}}))
    fig = _base(fig, f"{t('ch_bridge')} · {year} (mil M)", legend=False)
    fig.update_xaxes(tickangle=-20)
    return fig


def ratio_lines(analysis, codes, title, t, lang, percent=True):
    rows = {r.spec.code: r for r in analysis.ratio_rows}
    fig = go.Figure()
    for color, code in zip(theme.SERIES, codes):
        r = rows[code]
        fig.add_scatter(x=[str(y) for y in analysis.years], y=[r.values.get(y) for y in analysis.years], mode="lines+markers",
                        name=label_of(r.spec, lang) if len(label_of(r.spec, lang)) < 34 else (r.spec.short_es if lang == "es" else r.spec.short_en),
                        line={"color": color, "width": 3}, marker={"size": 8})
    fig = _base(fig, title)
    fig.update_yaxes(tickformat=".0%" if percent else ".1f")
    return fig


def balance_stack(analysis, t):
    data = balance_composition(analysis)
    x = [str(d["year"]) for d in data]
    fig = go.Figure()
    for key, name, color in (("reserves", t("bal_reserves"), theme.NAVY), ("other", t("bal_other_liab"), theme.SLATE), ("equity", t("bal_equity"), theme.TEAL)):
        fig.add_bar(x=x, y=[d[key] / 1e9 for d in data], name=name, marker_color=color)
    fig = _base(fig, t("ch_balance"))
    fig.update_layout(barmode="stack")
    return fig


def indicator_trend(analysis, code, lang, highlight=None):
    r = next(r for r in analysis.ratio_rows if r.spec.code == code)
    ys = [str(y) for y in analysis.years]
    colors = [theme.AMBER if y == highlight else theme.NAVY for y in analysis.years]
    pct = r.spec.unit == "pct"
    vals = [r.values.get(y) for y in analysis.years]
    fig = go.Figure(go.Bar(x=ys, y=vals, marker_color=colors,
                           text=[("" if v is None else (f"{v * 100:.1f}%" if pct else f"{v:.2f}x")) for v in vals], textposition="outside"))
    fig = _base(fig, label_of(r.spec, lang), height=300, legend=False)
    fig.update_yaxes(tickformat=".0%" if pct else ".1f")
    return fig


def projection_monthly(proj, t, color):
    x = [f"{t('month')} {m.month}" for m in proj.months]
    fig = go.Figure()
    fig.add_bar(x=x, y=[m.value / 1e9 for m in proj.months], marker_color=color, name=t("projected"))
    return _base(fig, f"{t('proj_monthly_table')} {proj.horizon_year} (mil M)", legend=False)


def projection_annual(proj, scenarios, t, color):
    years = [str(y) for y in proj.years]
    fig = go.Figure()
    fig.add_bar(x=years, y=[v / 1e9 for v in proj.values], name=t("history"), marker_color=theme.SLATE)
    target = str(proj.horizon_year)
    for i, sc in enumerate(scenarios):
        fig.add_scatter(x=[target], y=[sc.total / 1e9], mode="markers+text", name=sc.name,
                        marker={"size": 14 if sc.key == "reference" else 11, "color": color if sc.key == "reference" else theme.SERIES[(i + 2) % 6],
                                "symbol": "diamond" if sc.key == "reference" else "circle", "line": {"width": 1, "color": "#fff"}},
                        text=[f"{sc.total / 1e9:,.1f}"], textposition="middle right")
    fig = _base(fig, f"{t('proj_scenarios')} (mil M)", height=360)
    fig.update_xaxes(categoryorder="array", categoryarray=years + [target])
    return fig
