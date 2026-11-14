"""Visual identity: palette, CSS and the shared Plotly layout."""

NAVY, TEAL, AMBER, RED, GREEN, GREY, SLATE = "#1F3A5F", "#1B998B", "#F2A541", "#C8553D", "#1B7F5C", "#8A94A6", "#B8C2D1"
SERIES = [NAVY, TEAL, AMBER, RED, "#6C5B7B", "#3E92CC"]

CSS = """
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 3rem; max-width: 1280px;}
h1, h2, h3 {color: #1F3A5F; letter-spacing: -0.01em;}
.hero {background: linear-gradient(120deg, #1F3A5F 0%, #27517f 60%, #1B998B 130%); color: #fff; border-radius: 16px;
       padding: 22px 28px; margin-bottom: 18px;}
.hero h1 {color: #fff; margin: 0; font-size: 1.75rem;}
.hero p {margin: 4px 0 0 0; opacity: .85; font-size: .95rem;}
.hero .chips {margin-top: 12px;}
.chip {display: inline-block; background: rgba(255,255,255,.16); border-radius: 999px; padding: 3px 12px; margin: 0 6px 4px 0; font-size: .8rem;}
.kpi {background: #fff; border: 1px solid #E3E8EF; border-radius: 14px; padding: 14px 16px 12px 16px; height: 100%;
      box-shadow: 0 1px 2px rgba(31,58,95,.05);}
.kpi .label {font-size: .74rem; color: #6B7689; text-transform: uppercase; letter-spacing: .04em; min-height: 2.1em;}
.kpi .value {font-size: 1.9rem; font-weight: 700; color: #1F3A5F; line-height: 1.15; margin: 2px 0 4px 0;}
.kpi .delta {font-size: .82rem; font-weight: 600;}
.kpi .delta.good {color: #1B7F5C;} .kpi .delta.bad {color: #C8553D;} .kpi .delta.neutral {color: #6B7689;}
.kpi .sub {font-size: .72rem; color: #8A94A6; font-weight: 400; margin-left: 4px;}
.insight {background: #fff; border: 1px solid #E3E8EF; border-left: 5px solid #8A94A6; border-radius: 10px; padding: 10px 14px; margin-bottom: 8px; font-size: .93rem;}
.insight.good {border-left-color: #1B7F5C;} .insight.bad {border-left-color: #C8553D;}
.insight.warn {border-left-color: #F2A541;} .insight.info {border-left-color: #3E92CC;}
.section-title {font-size: 1.05rem; font-weight: 700; color: #1F3A5F; margin: 18px 0 8px 0;}
.note {font-size: .82rem; color: #6B7689;}
table.ratios {width: 100%; border-collapse: collapse; font-size: .88rem; background: #fff; border-radius: 10px; overflow: hidden;}
table.ratios th {background: #1B998B; color: #fff; padding: 8px 10px; text-align: right; font-weight: 600;}
table.ratios th:first-child {text-align: left;}
table.ratios td {padding: 7px 10px; border-bottom: 1px solid #EDF1F6; text-align: right; font-variant-numeric: tabular-nums;}
table.ratios td:first-child {text-align: left;}
table.ratios tr.cat td {background: #EEF2F7; font-weight: 700; color: #1F3A5F; text-align: left;}
table.ratios td.sel {background: #FFF4DC; font-weight: 700;}
</style>
"""


def plotly_layout(title=None, height=340, legend=True):
    """Common figure layout (kept as a dict so it can be unit-tested without plotly)."""
    return {
        "title": {"text": title, "x": 0, "font": {"size": 15, "color": NAVY}} if title else None,
        "height": height,
        "margin": {"l": 10, "r": 10, "t": 50 if title else 16, "b": 70 if legend else 10},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": "Inter, Arial, sans-serif", "size": 12, "color": "#1F2A3C"},
        "showlegend": legend,
        "legend": {"orientation": "h", "yanchor": "bottom", "y": -0.28, "x": 0},
        "hoverlabel": {"bgcolor": "#fff"},
    }
