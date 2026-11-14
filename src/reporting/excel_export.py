"""Excel export that mirrors the reference workbook (PIA_AnálisisFinanciero.xlsx).

Sheets: COMPARATIVO, DASHBOARD INTERACTIVO, PROYECCIÓN_VENTAS, SINIESTRALIDAD, VALIDACIÓN, LISTAS, BASE_ER, BASE_BG.

* BASE_ER / BASE_BG hold the extracted statements (inputs).
* COMPARATIVO, the projections and the dashboard are live formulas over those inputs, so editing a base cell
  recalculates everything. Every formula also carries its computed value, so viewers that do not recalculate
  (previews, some mobile apps) still show numbers.
* The workbook is written in Spanish, like the reference file.
"""
import io
import re

import xlsxwriter
from xlsxwriter.utility import xl_col_to_name

from src.financial_engine.catalog import CATALOG, CATEGORIES, PCT
from src.orchestrator.statements import INCOME_KEYS

NAVY, TEAL, AMBER, RED, GREY, LIGHT = "#1F3A5F", "#1B998B", "#F2A541", "#C8553D", "#8A94A6", "#EEF2F7"
FONT = "Arial"
DASH = "DASHBOARD INTERACTIVO"
PROJ_SALES = "PROYECCIÓN_VENTAS"
PROJ_CLAIMS = "SINIESTRALIDAD"

# Ratio definitions as Excel formulas over canonical concepts. Kept identical to the calculation engine;
# tests recalculate the workbook and compare every cell with the engine's result.
TEMPLATES = {
    "debt_to_assets": "{total_liabilities}/{total_assets}",
    "equity_ratio": "{total_equity}/{total_assets}",
    "solvency_total_assets_to_liabilities": "{total_assets}/{total_liabilities}",
    "leverage_liabilities_to_equity": "{total_liabilities}/{total_equity}",
    "leverage_technical_reserves_to_equity": "{technical_reserves}/{total_equity}",
    "leverage_reserve_change_to_equity": "{technical_reserves_change}/{total_equity}",
    "acquisition_cost_ratio": "{acquisition_costs}/{retained_premiums}",
    "claims_ratio": "{claims_incurred}/{net_premiums_earned}",
    "ceded_premium_ratio": "{ceded_premiums}/{gross_premiums_written}",
    "retention_ratio": "{retained_premiums}/{gross_premiums_written}",
    "ceded_reinsurance_commission_ratio": "{reinsurance_commissions_ceded}/{ceded_premiums}",
    "excess_loss_cover_ratio": "{excess_loss_cover}/{retained_premiums}",
    "return_on_equity": "{net_income}/{total_equity}",
    "return_on_paid_capital": "{net_income}/{paid_in_capital}",
    "return_on_paid_capital_plus_reserve": "{net_income}/({paid_in_capital}+{capital_reserve})",
    "net_margin_written_premiums": "{net_income}/{gross_premiums_written}",
    "net_margin_retained_premiums": "{net_income}/{retained_premiums}",
    "technical_margin": "{underwriting_result}/{net_premiums_earned}",
    "return_on_assets": "{net_income}/{total_assets}",
}

KPI_CODES = (
    "return_on_equity", "return_on_assets", "net_margin_written_premiums", "technical_margin",
    "claims_ratio", "acquisition_cost_ratio", "leverage_liabilities_to_equity", "leverage_technical_reserves_to_equity",
)
KPI_TITLES = {
    "return_on_equity": "ROE: Utilidad neta / Capital contable",
    "return_on_assets": "ROA: Utilidad neta / Activo total",
    "net_margin_written_premiums": "Utilidad neta / Primas emitidas",
    "technical_margin": "Resultado técnico / Primas devengadas",
    "claims_ratio": "Costo de siniestros / Primas devengadas",
    "acquisition_cost_ratio": "Costo de adquisición / Primas retenidas",
    "leverage_liabilities_to_equity": "Pasivo total / Capital contable",
    "leverage_technical_reserves_to_equity": "Reservas técnicas / Capital contable",
}

MONEY = '#,##0.00;[Red]-#,##0.00;"-"'
PCT_FMT = "0.00%"
TIMES_FMT = '0.00"x"'


def _delta_text(a, b, unit, year_b):
    """Same text the dashboard formula produces (used as the cached value)."""
    if a is None or b is None:
        return ""
    d = a - b
    arrow = "▲ " if d > 0 else ("▼ " if d < 0 else "► ")
    body = f"{abs(d) * 100:.2f} pp" if unit == PCT else f"{abs(d):.2f}x"
    return f"{arrow}{body} vs {year_b}"


def _display(v, unit):
    if v is None:
        return ""
    return f"{v * 100:.2f}%" if unit == PCT else f"{v:.2f}x"


class _Book:
    def __init__(self, analysis):
        self.a = analysis
        self.years = list(analysis.years)
        self.n = len(self.years)
        self.buf = io.BytesIO()
        self.wb = xlsxwriter.Workbook(self.buf, {"in_memory": True})
        self._fmt = {}
        self.rows = {}  # (sheet, key) -> excel row (1-based)

    # ---- formats
    def f(self, **props):
        base = {"font_name": FONT, "font_size": 10, "valign": "vcenter"}
        base.update(props)
        k = tuple(sorted(base.items()))
        if k not in self._fmt:
            self._fmt[k] = self.wb.add_format(base)
        return self._fmt[k]

    def title(self, ws, text, subtitle=None, width=8):
        ws.merge_range(0, 0, 0, width, text, self.f(bold=True, font_size=14, font_color="#FFFFFF", bg_color=NAVY))
        ws.set_row(0, 26)
        if subtitle:
            ws.write(1, 0, subtitle, self.f(italic=True, font_color=GREY))

    def ycol(self, base, j):
        return xl_col_to_name(base + j)

    # ---- locating concepts
    def locate(self, key):
        ex = self.a.extraction
        inc, bal = ex.income.first_row(key), ex.balance.first_row(key)
        if inc is not None and (key in INCOME_KEYS or bal is None):
            return "BASE_ER", self.rows.get(("BASE_ER", key))
        if bal is not None:
            return "BASE_BG", self.rows.get(("BASE_BG", key))
        return None

    # ---- BASE sheets
    def base_sheet(self, name, table, title):
        ws = self.wb.add_worksheet(name)
        ws.hide_gridlines(2)
        self.title(ws, f"{title} {self.years[0]}-{self.years[-1]}", f"{self.a.entity} · Cifras en pesos · Datos extraídos de los archivos cargados", self.n + 1)
        hdr = self.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", border=1)
        ws.write(3, 0, "Concepto", self.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, border=1))
        for j, y in enumerate(self.years):
            ws.write_string(3, 1 + j, str(y), hdr)
        ws.write(3, 1 + self.n, "Concepto normalizado", hdr)
        money = self.f(num_format=MONEY, border=1, border_color="#D9DFE8")
        text = self.f(border=1, border_color="#D9DFE8")
        keyf = self.f(font_color=GREY, italic=True, border=1, border_color="#D9DFE8")
        for i, row in enumerate(table.rows):
            r = 4 + i
            ws.write(r, 0, row.label, text)
            for j, y in enumerate(self.years):
                v = row.values.get(y)
                if v is None:
                    ws.write_blank(r, 1 + j, None, money)
                else:
                    ws.write_number(r, 1 + j, v, money)
            ws.write(r, 1 + self.n, row.key or "", keyf)
            if row.key and (name, row.key) not in self.rows:
                self.rows[(name, row.key)] = r + 1
        ws.set_column(0, 0, 72)
        ws.set_column(1, self.n, 20)
        ws.set_column(1 + self.n, 1 + self.n, 36)
        ws.freeze_panes(4, 1)
        return ws

    def ref(self, key, j):
        loc = self.locate(key)
        if loc is None or loc[1] is None:
            return None
        sheet, row = loc
        return f"{sheet}!{self.ycol(1, j)}{row}"

    def value(self, key, year):
        return self.a.data[year].get(key)


def build_workbook(analysis):
    """Return the .xlsx file content (bytes) for an Analysis."""
    b = _Book(analysis)
    wb, a, years, n = b.wb, analysis, b.years, b.n

    # Sheet creation order = tab order.
    ws_comp = wb.add_worksheet("COMPARATIVO")
    ws_dash = wb.add_worksheet(DASH)
    ws_sales = wb.add_worksheet(PROJ_SALES)
    ws_claims = wb.add_worksheet(PROJ_CLAIMS)
    ws_val = wb.add_worksheet("VALIDACIÓN")
    ws_list = wb.add_worksheet("LISTAS")
    # BASE sheets are created last but their rows are needed by formulas: build them first in memory order.
    ws_er = b.base_sheet("BASE_ER", a.extraction.income, "Estado de Resultados Consolidado")
    ws_bg = b.base_sheet("BASE_BG", a.extraction.balance, "Balance General Consolidado")

    _comparativo(b, ws_comp)
    _listas_and_dashboard(b, ws_list, ws_dash)
    _projection(b, ws_sales, PROJ_SALES, "PROYECCIÓN A 12 MESES · Proyección de ventas",
                "1. PROYECCIÓN DE VENTAS · PRIMAS EMITIDAS", [("Primas emitidas", "gross_premiums_written")],
                "gross_premiums_written", a.sales, a.sales_scenarios, first_data_row=6, month_header_row=13, concept_total="Primas proyectadas",
                chart_title="Primas emitidas: histórico y proyección")
    _projection(b, ws_claims, PROJ_CLAIMS, "PROYECCIÓN A 12 MESES · Siniestralidad",
                "2. SINIESTRALIDAD",
                [("Siniestralidad bruta", "gross_claims_incurred"),
                 ("Siniestralidad recuperada del reaseguro no proporcional (referencia)", "claims_recovered_nonproportional"),
                 ("Costo neto de siniestralidad (S)", "claims_incurred")],
                "claims_incurred", a.claims, a.claims_scenarios, first_data_row=6, month_header_row=15, concept_total="Siniestralidad proyectada",
                chart_title="Costo neto de siniestralidad: histórico y proyección")
    _validation(b, ws_val)
    for sheet in wb.worksheets():
        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 0)
    ws_dash.activate()
    wb.close()
    return b.buf.getvalue()


# --------------------------------------------------------------------------------------------------
def _comparativo(b, ws):
    a, years, n = b.a, b.years, b.n
    ws.hide_gridlines(2)
    b.title(ws, f"COMPARATIVO DE RAZONES FINANCIERAS | {years[0]}-{years[-1]}", f"{a.entity}", n + 2)
    hdr = b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", border=1)
    for c, text in enumerate(("Categoría", "Indicador", "Unidad")):
        ws.write(3, c, text, hdr)
    for j, y in enumerate(years):
        ws.write_string(3, 3 + j, str(y), hdr)
    for i, row in enumerate(a.ratio_rows):
        r, spec = 4 + i, row.spec
        shade = {"bg_color": LIGHT} if i % 2 else {}
        ws.write(r, 0, spec.category, b.f(border=1, border_color="#D9DFE8", **shade))
        ws.write(r, 1, spec.label_es, b.f(border=1, border_color="#D9DFE8", **shade))
        ws.write(r, 2, spec.unit_label_es, b.f(border=1, border_color="#D9DFE8", align="center", **shade))
        num = b.f(num_format=PCT_FMT if spec.unit == PCT else TIMES_FMT, border=1, border_color="#D9DFE8", **shade)
        for j, y in enumerate(years):
            value = row.values.get(y)
            tpl, refs = TEMPLATES[spec.code], {}
            for key in re.findall(r"\{(\w+)\}", tpl):
                refs[key] = b.ref(key, j)
            if any(v is None for v in refs.values()):
                ws.write_blank(r, 3 + j, None, num)
            else:
                ws.write_formula(r, 3 + j, "=IFERROR(" + tpl.format(**refs) + ',"")', num, "" if value is None else value)
    last = 4 + len(a.ratio_rows)
    note = ("Nota: los valores porcentuales se muestran como porcentaje; los indicadores de apalancamiento y rendimiento "
            "sobre capital pagado se muestran en veces. Cada celda es una fórmula sobre las hojas BASE_BG y BASE_ER.")
    ws.merge_range(last + 2, 0, last + 2, n + 2, note, b.f(italic=True, font_color=GREY, text_wrap=True))
    ws.set_row(last + 2, 30)
    ws.set_column(0, 0, 20)
    ws.set_column(1, 1, 62)
    ws.set_column(2, 2, 12)
    ws.set_column(3, 3 + n, 13)
    ws.freeze_panes(4, 3)


# --------------------------------------------------------------------------------------------------
def _listas_and_dashboard(b, ls, ds):
    a, years, n = b.a, b.years, b.n
    first, last_col = "D", xl_col_to_name(3 + n - 1)
    comp_years = f"COMPARATIVO!$D$4:${last_col}$4"
    r0, r1 = 5, 4 + len(a.ratio_rows)  # first/last ratio rows in COMPARATIVO
    cat_rng, ind_rng, unit_rng = (f"COMPARATIVO!$A${r0}:$A${r1}", f"COMPARATIVO!$B${r0}:$B${r1}", f"COMPARATIVO!$C${r0}:$C${r1}")
    val_rng = f"COMPARATIVO!$D${r0}:${last_col}${r1}"
    D = f"'{DASH}'"

    # ---------------- defaults for cached values
    year_a, year_b = years[-1], years[-2] if n > 1 else years[-1]
    pos_a, pos_b = years.index(year_a) + 1, years.index(year_b) + 1
    category = "Rentabilidad"
    indicator_spec = next(r.spec for r in a.ratio_rows if r.spec.code == "return_on_equity")
    cat_rows = [r for r in a.ratio_rows if r.spec.category == category]
    first_pos = next(i for i, r in enumerate(a.ratio_rows) if r.spec.category == category) + 1
    ind_row = next(i for i, r in enumerate(a.ratio_rows) if r.spec.code == indicator_spec.code) + 1
    scale = 100 if indicator_spec.unit == PCT else 1

    # ---------------- LISTAS (helper)
    ls.write(0, 0, "Hoja auxiliar del dashboard — se calcula sola, no es necesario editarla", b.f(bold=True, font_color=NAVY))
    labels = [
        ("Año de análisis", f"=TEXT({D}!$E$4,\"0\")", str(year_a)),
        ("Año de comparación", f"=TEXT({D}!$K$4,\"0\")", str(year_b)),
        ("Posición del año de análisis", f"=MATCH($B$3,{comp_years},0)", pos_a),
        ("Posición del año de comparación", f"=MATCH($B$4,{comp_years},0)", pos_b),
        ("Categoría seleccionada", f"={D}!$E$5", category),
        ("Indicador efectivo",
         f"=IF(COUNTIFS({cat_rng},$B$7,{ind_rng},{D}!$K$5)=0,INDEX({ind_rng},MATCH($B$7,{cat_rng},0)),{D}!$K$5)", indicator_spec.label_es),
        ("Fila del indicador", f"=MATCH($B$8,{ind_rng},0)", ind_row),
        ("Unidad del indicador", f"=INDEX({unit_rng},$B$9)", indicator_spec.unit_label_es),
        ("Escala de visualización", '=IF($B$10="Porcentaje",100,1)', scale),
        ("Núm. de indicadores en la categoría", f"=COUNTIF({cat_rng},$B$7)", len(cat_rows)),
        ("Posición del primer indicador de la categoría", f"=MATCH($B$7,{cat_rng},0)", first_pos),
    ]
    for i, (label, formula, cached) in enumerate(labels):
        ls.write(2 + i, 0, label, b.f(bold=True))
        ls.write_formula(2 + i, 1, formula, b.f(), cached)
    # chart data block
    base = 15
    for c, text in enumerate(("Año", "Valor", "Año de análisis", "Año de comparación", "Otros años")):
        ls.write(base, 3 + c, text, b.f(bold=True, bg_color=LIGHT))
    ind_vals = a.ratio_rows[ind_row - 1].values
    for j, y in enumerate(years):
        r = base + 1 + j
        v = ind_vals.get(y)
        scaled = None if v is None else v * scale
        ls.write_formula(r, 3, f"=COMPARATIVO!{b.ycol(3, j)}$4", b.f(), str(y))
        ls.write_formula(r, 4, f"=INDEX({val_rng},$B$9,{j + 1})*$B$11", b.f(num_format="0.00"), scaled if scaled is not None else 0)
        ls.write_formula(r, 5, f"=IF(D{r + 1}=$B$3,E{r + 1},0)", b.f(num_format="0.00"), scaled if (str(y) == str(year_a) and scaled is not None) else 0)
        ls.write_formula(r, 6, f"=IF(AND(D{r + 1}=$B$4,D{r + 1}<>$B$3),E{r + 1},0)", b.f(num_format="0.00"),
                         scaled if (str(y) == str(year_b) and year_b != year_a and scaled is not None) else 0)
        ls.write_formula(r, 7, f"=IF(OR(D{r + 1}=$B$3,D{r + 1}=$B$4),0,E{r + 1})", b.f(num_format="0.00"),
                         0 if str(y) in (str(year_a), str(year_b)) or scaled is None else scaled)
    ls.set_column(0, 0, 44)
    ls.set_column(1, 1, 48)
    ls.set_column(3, 7, 18)

    # ---------------- DASHBOARD
    ds.hide_gridlines(2)
    ds.set_column(0, 0, 2)
    ds.set_column(1, 13, 12.5)
    ds.merge_range("B1:N2", f"{a.entity} · {years[0]}-{years[-1]}      RAZONES FINANCIERAS",
                   b.f(bold=True, font_size=18, font_color="#FFFFFF", bg_color=NAVY, indent=1))
    lab = b.f(bold=True, font_color=NAVY)
    sel = b.f(bold=True, bg_color="#FFF4DC", border=1, border_color=AMBER, align="center")
    ds.write("B4", "Año de análisis", lab)
    ds.write_number("E4", year_a, sel)
    ds.write("I4", "Año de comparación", lab)
    ds.write_number("K4", year_b, sel)
    ds.write("B5", "Categoría de razones", lab)
    ds.write("E5", category, sel)
    ds.write("I5", "Indicador", lab)
    ds.merge_range("K5:N5", indicator_spec.label_es, sel)
    ds.data_validation("E4", {"validate": "list", "source": [str(y) for y in years]})
    ds.data_validation("K4", {"validate": "list", "source": [str(y) for y in years]})
    ds.data_validation("E5", {"validate": "list", "source": list(CATEGORIES)})
    ds.data_validation("K5", {"validate": "list", "source": f"=COMPARATIVO!$B${r0}:$B${r1}"})
    ds.write("B6", "Cambia los cuatro campos amarillos para recalcular todo el tablero.", b.f(italic=True, font_color=GREY))

    green, red, grey = b.f(font_color="#1B7F5C", bold=True), b.f(font_color=RED, bold=True), b.f(font_color=GREY, bold=True)
    spec_by_code = {r.spec.code: (i, r) for i, r in enumerate(a.ratio_rows)}
    positions = [("B", "D"), ("E", "G"), ("H", "J"), ("K", "M")]
    for k, code in enumerate(KPI_CODES):
        i, row = spec_by_code[code]
        spec = row.spec
        top = 8 if k < 4 else 12
        c0, c1 = positions[k % 4]
        crow = r0 + i
        ds.merge_range(f"{c0}{top}:{c1}{top}", KPI_TITLES[code], b.f(bold=True, font_size=9, font_color=GREY, bg_color=LIGHT, align="center", top=1, left=1, right=1, border_color="#D9DFE8"))
        va, vb = row.values.get(year_a), row.values.get(year_b)
        numfmt = "0.0%" if spec.unit == PCT else '0.00"x"'
        ds.merge_range(f"{c0}{top + 1}:{c1}{top + 1}", "", b.f(bold=True, font_size=20, font_color=NAVY, bg_color=LIGHT, align="center", num_format=numfmt, left=1, right=1, border_color="#D9DFE8"))
        ds.write_formula(f"{c0}{top + 1}", f"=INDEX(COMPARATIVO!$D${crow}:${last_col}${crow},LISTAS!$B$5)",
                         b.f(bold=True, font_size=20, font_color=NAVY, bg_color=LIGHT, align="center", num_format=numfmt, left=1, right=1, border_color="#D9DFE8"),
                         "" if va is None else va)
        cell = f"{c0}{top + 1}"
        comp = f"INDEX(COMPARATIVO!$D${crow}:${last_col}${crow},LISTAS!$B$6)"
        body = 'TEXT(ABS({0}-{1})*100,"0.00")&" pp vs "&LISTAS!$B$4'.format(cell, comp) if spec.unit == PCT else \
            'TEXT(ABS({0}-{1}),"0.00")&"x vs "&LISTAS!$B$4'.format(cell, comp)
        formula = f'=IF({cell}>{comp},"▲ ",IF({cell}<{comp},"▼ ","► "))&{body}'
        dfmt = b.f(font_size=10, align="center", bg_color=LIGHT, bottom=1, left=1, right=1, border_color="#D9DFE8")
        ds.merge_range(f"{c0}{top + 2}:{c1}{top + 2}", "", dfmt)
        ds.write_formula(f"{c0}{top + 2}", formula, dfmt, _delta_text(va, vb, spec.unit, year_b))
        up_good = {"up": ("▲", "▼"), "down": ("▼", "▲")}.get(spec.direction)
        target = f"{c0}{top + 2}"
        if up_good:
            ds.conditional_format(target, {"type": "text", "criteria": "begins with", "value": up_good[0], "format": green})
            ds.conditional_format(target, {"type": "text", "criteria": "begins with", "value": up_good[1], "format": red})
        else:
            ds.conditional_format(target, {"type": "text", "criteria": "begins with", "value": "▲", "format": grey})
            ds.conditional_format(target, {"type": "text", "criteria": "begins with", "value": "▼", "format": grey})
    ds.set_row(8, 30)
    ds.set_row(12, 30)

    ds.write_formula("B16", '="Año de análisis: "&LISTAS!$B$3&"  ·  Comparación: "&LISTAS!$B$4', b.f(bold=True, font_color=NAVY),
                     f"Año de análisis: {year_a}  ·  Comparación: {year_b}")
    unit_word = '"%"' if indicator_spec.unit == PCT else '"veces"'
    ds.write_formula("B18", '="Indicador seleccionado: "&LISTAS!$B$8&" ("&IF(LISTAS!$B$10="Porcentaje","%","veces")&")"',
                     b.f(bold=True, font_color=NAVY), f"Indicador seleccionado: {indicator_spec.label_es} ({'%' if indicator_spec.unit == PCT else 'veces'})")
    ds.write("H18", f"Razones clave {years[0]}-{years[-1]} (porcentaje)", b.f(bold=True, font_color=NAVY))

    # chart 1: selected indicator, years coloured by role
    c1 = b.wb.add_chart({"type": "column", "subtype": "stacked"})
    rng = lambda col: f"=LISTAS!${col}${base + 2}:${col}${base + 1 + n}"
    for col, name, color in (("F", "Año de análisis", NAVY), ("G", "Año de comparación", AMBER), ("H", "Otros años", "#B8C2D1")):
        c1.add_series({"name": name, "categories": rng("D"), "values": rng(col), "fill": {"color": color}, "gap": 60})
    c1.set_legend({"position": "bottom", "overlay": False})
    c1.set_title({"none": True})
    c1.set_chartarea({"border": {"none": True}})
    c1.set_size({"width": 540, "height": 300})
    c1.show_na_as_empty_cell() if hasattr(c1, "show_na_as_empty_cell") else None
    ds.insert_chart("B19", c1)

    # chart 2: key percentage ratios over time
    c2 = b.wb.add_chart({"type": "line"})
    palette = (NAVY, TEAL, AMBER, RED)
    for color, code in zip(palette, ("return_on_equity", "return_on_assets", "net_margin_written_premiums", "technical_margin")):
        i, row = spec_by_code[code]
        crow = r0 + i
        c2.add_series({"name": f"=COMPARATIVO!$B${crow}", "categories": f"={comp_years}",
                       "values": f"=COMPARATIVO!$D${crow}:${last_col}${crow}",
                       "line": {"color": color, "width": 2.25}, "marker": {"type": "circle", "size": 6, "fill": {"color": color}, "border": {"color": color}}})
    c2.set_legend({"position": "bottom", "overlay": False})
    c2.set_x_axis({"label_position": "low"})
    c2.set_y_axis({"num_format": "0%", "major_gridlines": {"visible": True, "line": {"color": "#E3E8EF"}}})
    c2.set_title({"none": True})
    c2.set_chartarea({"border": {"none": True}})
    c2.set_size({"width": 620, "height": 300})
    ds.insert_chart("H19", c2)

    # category table
    ds.write_formula("B34", '="Indicadores de la categoría: "&LISTAS!$B$7', b.f(bold=True, font_color=NAVY), f"Indicadores de la categoría: {category}")
    th = b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", border=1)
    ds.merge_range("B35:F35", "Indicador", th)
    ds.merge_range("G35:H35", "Año de análisis", th)
    ds.merge_range("I35:J35", "Año de comparación", th)
    ds.merge_range("K35:M35", "Variación", th)
    body = b.f(border=1, border_color="#D9DFE8")
    bodyc = b.f(border=1, border_color="#D9DFE8", align="center")
    for k in range(7):
        r = 36 + k
        cached_label = cat_rows[k].spec.label_es if k < len(cat_rows) else ""
        spec = cat_rows[k].spec if k < len(cat_rows) else None
        va = cat_rows[k].values.get(year_a) if spec else None
        vb = cat_rows[k].values.get(year_b) if spec else None
        idx = f"LISTAS!$B$13+{k}"
        ds.merge_range(f"B{r}:F{r}", "", body)
        ds.write_formula(f"B{r}", f'=IF({k + 1}<=LISTAS!$B$12,INDEX({ind_rng},{idx}),"")', body, cached_label)
        unit = f"INDEX({unit_rng},{idx})"
        for c0, c1_, pos, val in (("G", "H", "LISTAS!$B$5", va), ("I", "J", "LISTAS!$B$6", vb)):
            ds.merge_range(f"{c0}{r}:{c1_}{r}", "", bodyc)
            v = f"INDEX({val_rng},{idx},{pos})"
            ds.write_formula(f"{c0}{r}", f'=IF($B{r}="","",IF({unit}="Porcentaje",TEXT({v},"0.00%"),TEXT({v},"0.00")&"x"))', bodyc,
                             _display(val, spec.unit) if spec else "")
        ds.merge_range(f"K{r}:M{r}", "", bodyc)
        va_f, vb_f = f"INDEX({val_rng},{idx},LISTAS!$B$5)", f"INDEX({val_rng},{idx},LISTAS!$B$6)"
        delta = f"({va_f}-{vb_f})"
        ds.write_formula(
            f"K{r}",
            f'=IF($B{r}="","",IF({delta}>0,"▲ ",IF({delta}<0,"▼ ","► "))&IF({unit}="Porcentaje",TEXT(ABS({delta})*100,"0.00")&" pp",TEXT(ABS({delta}),"0.00")&"x"))',
            bodyc, (_delta_text(va, vb, spec.unit, "").replace(" vs ", "")) if spec else "")


# --------------------------------------------------------------------------------------------------
def _projection(b, ws, name, title, section, rows, series_key, proj, scenarios, first_data_row, month_header_row, concept_total, chart_title):
    """Projection sheet laid out like the reference workbook (same cell positions)."""
    a, years, n = b.a, b.years, b.n
    ws.hide_gridlines(2)
    b.title(ws, title, f"{a.entity} · método: promedio aritmético de variaciones anuales / 12, compuesto mes a mes", n + 4)
    ws.write(3, 0, section, b.f(bold=True, font_color=NAVY, font_size=11))
    hdr = b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", border=1)
    ws.write(4, 0, "Concepto", b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, border=1))
    for j, y in enumerate(years):
        ws.write_string(4, 1 + j, str(y), hdr)
    money = b.f(num_format=MONEY, border=1, border_color="#D9DFE8")
    pctf = b.f(num_format=PCT_FMT, border=1, border_color="#D9DFE8")
    text = b.f(border=1, border_color="#D9DFE8")
    last = b.ycol(1, n - 1)

    if proj is None:
        ws.write(5, 0, "No hay datos suficientes para proyectar (se requieren al menos dos años).", b.f(italic=True))
        return
    # input rows
    r = first_data_row - 1  # zero-based row index of first input row
    for label, key in rows:
        ws.write(r, 0, label + " ", text)
        for j, y in enumerate(years):
            ref = b.ref(key, j)
            v = a.data[y].get(key)
            if ref is None:
                ws.write_blank(r, 1 + j, None, money)
            else:
                ws.write_formula(r, 1 + j, f"={ref}", money, 0 if v is None else v)
        r += 1
    series_row = r  # zero-based row of the projected series (last input row)
    s_xl = series_row  # 1-based Excel row of the series = series_row (zero-based +1) -> series_row
    s_excel = series_row  # the row just written is index series_row-1 -> excel row series_row
    ws.write(series_row, 0, "Variación anual  ", text)
    ws.write_string(series_row, 1, "-", b.f(align="center", border=1, border_color="#D9DFE8"))
    values = proj.values
    yoy = proj.yoy
    for j in range(1, n):
        prev, cur = b.ycol(1, j - 1), b.ycol(1, j)
        ws.write_formula(series_row, 1 + j, f"={cur}{s_excel}/{prev}{s_excel}-1", pctf, 0 if yoy[j] is None else yoy[j])
    var_row = series_row + 1  # excel row of "Variación anual"
    t_row = series_row + 1    # zero-based row for helper t index
    ws.write(t_row, 0, "Índice de año (t, para tendencia lineal)", b.f(font_color=GREY, italic=True))
    for j in range(n):
        ws.write_number(t_row, 1 + j, j + 1, b.f(font_color=GREY, italic=True, align="center"))
    t_excel = t_row + 1
    avg_row = t_row + 1  # zero-based; keeps B9/B10/B11 and the monthly table at the reference positions
    ws.write(avg_row, 0, "Promedio aritmético de crecimiento (ḡ)", b.f(bold=True, border=1, border_color="#D9DFE8"))
    ws.write_formula(avg_row, 1, f"=AVERAGE(C{var_row}:{last}{var_row})", b.f(num_format="0.0000%", bold=True, border=1, border_color="#D9DFE8"), proj.mean_growth)
    ws.write(avg_row + 1, 0, "Tasa mensual  ", text)
    ws.write_formula(avg_row + 1, 1, f"=B{avg_row + 1}/12", b.f(num_format="0.0000%", border=1, border_color="#D9DFE8"), proj.monthly_rate)
    ws.write(avg_row + 2, 0, f"Base mensual  {series_label(rows)} {years[-1]} / 12", text)
    ws.write_formula(avg_row + 2, 1, f"={last}{s_excel}/12", money, proj.monthly_base)
    rate_cell, base_cell = f"$B${avg_row + 2}", f"$B${avg_row + 3}"

    # monthly table
    mh = avg_row + 4
    for c, t in enumerate(("Mes", concept_total, "Tasa mensual utilizada", f"Variación acumulada vs. promedio mensual {years[-1]}")):
        ws.write(mh, c, t, b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", text_wrap=True, border=1))
    ws.set_row(mh, 32)
    for k, point in enumerate(proj.months):
        rr = mh + 1 + k
        ws.write(rr, 0, f"Mes {k + 1}", text)
        prev = base_cell if k == 0 else f"B{rr}"
        ws.write_formula(rr, 1, f"={prev}*(1+C{rr + 1})", money, point.value)
        ws.write_formula(rr, 2, f"={rate_cell}", b.f(num_format="0.0000%", border=1, border_color="#D9DFE8"), point.rate)
        ws.write_formula(rr, 3, f"=B{rr + 1}/{base_cell}-1", pctf, point.cumulative_vs_base)
    tr = mh + 13
    first_m, last_m = mh + 2, mh + 13
    tot = b.f(bold=True, num_format=MONEY, bg_color=LIGHT, border=1, border_color="#D9DFE8")
    ws.write(tr, 0, "Total 12 meses", b.f(bold=True, bg_color=LIGHT, border=1, border_color="#D9DFE8"))
    ws.write_formula(tr, 1, f"=SUM(B{first_m}:B{last_m})", tot, proj.total)
    ws.write_blank(tr, 2, None, b.f(bg_color=LIGHT, border=1, border_color="#D9DFE8"))
    ws.write_formula(tr, 3, f"=B{tr + 1}/{last}{s_excel}-1", b.f(bold=True, num_format=PCT_FMT, bg_color=LIGHT, border=1, border_color="#D9DFE8"), proj.total_growth)
    total_cell = f"B{tr + 1}"

    # alternative annual scenarios
    sr = tr + 3
    ws.write(sr, 0, f"Escenarios alternos (anual {proj.horizon_year}) — comparación del método del Excel", b.f(bold=True, font_color=NAVY, font_size=11))
    for c, t in enumerate(("Método", f"Proyección {proj.horizon_year}", f"Variación vs. {years[-1]}", "Descripción")):
        ws.write(sr + 1, c, t, b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", border=1))
    first_cell = f"B{s_excel}"
    last_cell = f"{last}{s_excel}"
    growth_avg = f"$B${avg_row + 1}"
    formulas = {
        "reference": f"={total_cell}",
        "annual_mean": f"={last_cell}*(1+{growth_avg})",
        "cagr": f"={last_cell}*({last_cell}/{first_cell})^(1/{n - 1})",
        "linear": f"=FORECAST({n + 1},B{s_excel}:{last}{s_excel},B{t_excel}:{last}{t_excel})",
    }
    for k, sc in enumerate(scenarios):
        rr = sr + 2 + k
        ws.write(rr, 0, sc.name, text)
        ws.write_formula(rr, 1, formulas[sc.key], money, sc.total)
        ws.write_formula(rr, 2, f"=B{rr + 1}/{last_cell}-1", pctf, sc.growth)
        ws.write(rr, 3, sc.description, b.f(text_wrap=True, border=1, border_color="#D9DFE8", font_size=9))
        ws.set_row(rr, 36)
    note_r = sr + 2 + len(scenarios) + 1
    ws.merge_range(note_r, 0, note_r, 3,
                   "Lectura: el método del Excel parte del promedio mensual del último año y compone la tasa anual/12, por lo que su total "
                   "queda por debajo del crecimiento anual promedio. Con solo cinco observaciones anuales y sin estacionalidad, todas las cifras son indicativas.",
                   b.f(italic=True, font_color=GREY, text_wrap=True, font_size=9))
    ws.set_row(note_r, 42)
    ws.set_column(0, 0, 58)
    ws.set_column(1, max(n, 3), 22)
    ws.set_column(3, 3, 44)

    # charts
    c1 = b.wb.add_chart({"type": "column"})
    cats = f"='{name}'!$B$5:${last}$5"
    c1.add_series({"name": "Histórico", "categories": cats, "values": f"='{name}'!$B${s_excel}:${last}${s_excel}", "fill": {"color": NAVY}, "gap": 60})
    c1.set_title({"name": chart_title, "name_font": {"size": 11, "name": FONT}, "overlay": False})
    c1.set_legend({"none": True})
    c1.set_chartarea({"border": {"none": True}})
    c1.set_size({"width": 520, "height": 280})
    ws.insert_chart(3, n + 3, c1)
    c2 = b.wb.add_chart({"type": "line"})
    c2.add_series({"name": "Proyección mensual", "categories": f"='{name}'!$A${mh + 2}:$A${last_m}", "values": f"='{name}'!$B${mh + 2}:$B${last_m}",
                   "line": {"color": TEAL, "width": 2.5}, "marker": {"type": "circle", "size": 5, "fill": {"color": TEAL}, "border": {"color": TEAL}}})
    c2.set_title({"name": "Proyección mensual (12 meses)", "name_font": {"size": 11, "name": FONT}, "overlay": False})
    c2.set_legend({"none": True})
    c2.set_chartarea({"border": {"none": True}})
    c2.set_size({"width": 520, "height": 280})
    ws.insert_chart(18, n + 3, c2)


def series_label(rows):
    return rows[-1][0]


# --------------------------------------------------------------------------------------------------
def _validation(b, ws):
    a = b.a
    ws.hide_gridlines(2)
    b.title(ws, "VALIDACIÓN CONTABLE Y DE EXTRACCIÓN", f"{a.entity} · identidades que deben cumplirse en un par balance/estado de resultados correctamente leído", 5)
    hdr = b.f(bold=True, font_color="#FFFFFF", bg_color=TEAL, align="center", border=1)
    for c, t in enumerate(("Año", "Verificación", "Esperado", "Reportado", "Diferencia", "Estado")):
        ws.write(3, c, t, hdr)
    ok, bad = b.f(font_color="#1B7F5C", bold=True, align="center", border=1), b.f(font_color=RED, bold=True, align="center", border=1)
    money = b.f(num_format=MONEY, border=1, border_color="#D9DFE8")
    text = b.f(border=1, border_color="#D9DFE8")
    r = 4
    for c in a.checks:
        ws.write_number(r, 0, c["year"], b.f(border=1, border_color="#D9DFE8", align="center", num_format="0"))
        ws.write(r, 1, c["check"], text)
        ws.write_number(r, 2, c["expected"], money)
        ws.write_number(r, 3, c["actual"], money)
        ws.write_number(r, 4, c["difference"], money)
        ws.write(r, 5, c["status"], ok if c["status"] == "OK" else bad)
        r += 1
    r += 1
    ws.write(r, 0, "Archivos procesados", b.f(bold=True, font_color=NAVY))
    r += 1
    for item in a.extraction.files:
        ws.write(r, 0, item["year"], b.f(num_format="0", align="center"))
        ws.write(r, 1, f"{item['name']} ({'balance' if item['kind'] == 'balance' else 'estado de resultados'}, detectado por {'encabezado' if item['source'] == 'header' else 'nombre de archivo'})")
        r += 1
    if a.proxies:
        r += 1
        ws.write(r, 0, "Aproximaciones aplicadas", b.f(bold=True, font_color=NAVY))
        r += 1
        for p in a.proxies:
            ws.write(r, 0, p["year"], b.f(num_format="0", align="center"))
            ws.write(r, 1, p["note"])
            r += 1
    ws.set_column(0, 0, 10)
    ws.set_column(1, 1, 78)
    ws.set_column(2, 4, 22)
    ws.set_column(5, 5, 12)
