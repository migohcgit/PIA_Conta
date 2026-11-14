"""Catalog of the 19 reference ratios (sheet COMPARATIVO of PIA_AnálisisFinanciero.xlsx).

Each entry points at a ratio produced by the existing calculation engine (``ratios.py`` and
``insurer_ratios.py``); this module only adds presentation metadata: category, bilingual label,
unit and the direction that is considered favourable. Ratios are stored as decimals (0.85 = 85%).
"""
from dataclasses import dataclass

PCT, TIMES = "pct", "x"
SOLVENCY, TECHNICAL, PROFITABILITY = "Solvencia", "Operación técnica", "Rentabilidad"
CATEGORIES = (SOLVENCY, TECHNICAL, PROFITABILITY)
CATEGORY_EN = {SOLVENCY: "Solvency", TECHNICAL: "Technical operation", PROFITABILITY: "Profitability"}


@dataclass(frozen=True)
class RatioSpec:
    code: str            # engine ratio name
    category: str
    label_es: str        # exactly as in the reference workbook
    label_en: str
    unit: str            # PCT | TIMES
    direction: str | None  # "up" = higher is favourable, "down" = lower is favourable, None = neutral
    short_es: str
    short_en: str
    meaning_es: str
    meaning_en: str

    @property
    def unit_label_es(self):
        return "Porcentaje" if self.unit == PCT else "Veces"


CATALOG = (
    RatioSpec("debt_to_assets", SOLVENCY, "Pasivo total / Activo total", "Total liabilities / Total assets", PCT, "down",
              "Pasivo / Activo", "Liabilities / Assets",
              "Proporción de los activos financiada con obligaciones (incluye reservas técnicas).",
              "Share of assets financed by obligations (including technical reserves)."),
    RatioSpec("equity_ratio", SOLVENCY, "Capital contable / Activo total", "Equity / Total assets", PCT, "up",
              "Capital / Activo", "Equity / Assets",
              "Proporción de los activos respaldada por capital propio.",
              "Share of assets backed by own equity."),
    RatioSpec("solvency_total_assets_to_liabilities", SOLVENCY, "Activo total / Pasivo total", "Total assets / Total liabilities", TIMES, "up",
              "Activo / Pasivo", "Assets / Liabilities",
              "Veces que el activo total cubre el pasivo total.",
              "Times total assets cover total liabilities."),
    RatioSpec("leverage_liabilities_to_equity", SOLVENCY, "Pasivo total / Capital contable", "Total liabilities / Equity", TIMES, "down",
              "Pasivo / Capital", "Liabilities / Equity",
              "Apalancamiento: pesos de pasivo por cada peso de capital.",
              "Leverage: liabilities per unit of equity."),
    RatioSpec("leverage_technical_reserves_to_equity", SOLVENCY, "Reservas técnicas / Capital contable", "Technical reserves / Equity", TIMES, "down",
              "Reservas técnicas / Capital", "Technical reserves / Equity",
              "Peso de las reservas técnicas respecto al capital.",
              "Weight of technical reserves relative to equity."),
    RatioSpec("leverage_reserve_change_to_equity", SOLVENCY, "Cambio de reservas técnicas / Capital contable", "Change in technical reserves / Equity", TIMES, None,
              "Cambio de reservas / Capital", "Reserve change / Equity",
              "Incremento neto de la reserva de riesgos en curso del ejercicio respecto al capital.",
              "Net increase in the unearned-risk reserve for the year relative to equity."),
    RatioSpec("acquisition_cost_ratio", TECHNICAL, "Costos netos de adquisición / Primas retenidas", "Net acquisition costs / Retained premiums", PCT, "down",
              "Costo de adquisición / Primas retenidas", "Acquisition cost / Retained premiums",
              "Comisiones y costos de colocación por peso de prima retenida.",
              "Commissions and placement costs per unit of retained premium."),
    RatioSpec("claims_ratio", TECHNICAL, "Costo neto de siniestros / Primas netas devengadas retenidas", "Net claims cost / Net earned retained premiums", PCT, "down",
              "Siniestralidad", "Claims ratio",
              "Costo neto de siniestros por peso de prima devengada retenida.",
              "Net claims cost per unit of earned retained premium."),
    RatioSpec("ceded_premium_ratio", TECHNICAL, "Primas cedidas / Primas emitidas", "Ceded premiums / Written premiums", PCT, None,
              "Primas cedidas / emitidas", "Ceded / Written",
              "Proporción de la prima emitida que se cede al reaseguro.",
              "Share of written premium ceded to reinsurers."),
    RatioSpec("retention_ratio", TECHNICAL, "Primas retenidas / Primas emitidas", "Retained premiums / Written premiums", PCT, None,
              "Retención", "Retention",
              "Proporción de la prima emitida que la compañía retiene.",
              "Share of written premium retained by the company."),
    RatioSpec("ceded_reinsurance_commission_ratio", TECHNICAL, "Comisiones de reaseguro cedido / Primas cedidas", "Ceded reinsurance commissions / Ceded premiums", PCT, "up",
              "Comisiones de reaseguro / Cedidas", "Reinsurance commissions / Ceded",
              "Comisión que el reasegurador reconoce por cada peso cedido.",
              "Commission recognised by reinsurers per unit ceded."),
    RatioSpec("excess_loss_cover_ratio", TECHNICAL, "Cobertura de exceso de pérdida / Primas retenidas", "Excess-of-loss cover / Retained premiums", PCT, None,
              "Exceso de pérdida / Retenidas", "Excess-of-loss / Retained",
              "Costo de la cobertura de exceso de pérdida respecto a la prima retenida.",
              "Cost of excess-of-loss cover relative to retained premium."),
    RatioSpec("return_on_equity", PROFITABILITY, "Utilidad neta / Capital contable (ROE)", "Net income / Equity (ROE)", PCT, "up",
              "ROE", "ROE",
              "Utilidad generada por cada peso de capital contable.",
              "Profit generated per unit of equity."),
    RatioSpec("return_on_paid_capital", PROFITABILITY, "Utilidad neta / Capital pagado", "Net income / Paid-in capital", TIMES, "up",
              "Utilidad / Capital pagado", "Net income / Paid-in capital",
              "Utilidad neta frente al capital social pagado.",
              "Net income relative to paid-in share capital."),
    RatioSpec("return_on_paid_capital_plus_reserve", PROFITABILITY, "Utilidad neta / (Capital pagado + Reserva de capital)", "Net income / (Paid-in capital + Capital reserve)", TIMES, "up",
              "Utilidad / (Capital pagado + Reserva)", "Net income / (Paid-in + Reserve)",
              "Utilidad neta frente al capital pagado más la reserva legal.",
              "Net income relative to paid-in capital plus legal reserve."),
    RatioSpec("net_margin_written_premiums", PROFITABILITY, "Utilidad neta / Primas emitidas", "Net income / Written premiums", PCT, "up",
              "Utilidad / Primas emitidas", "Net income / Written premiums",
              "Margen neto sobre la prima emitida.",
              "Net margin on written premium."),
    RatioSpec("net_margin_retained_premiums", PROFITABILITY, "Utilidad neta / Primas retenidas", "Net income / Retained premiums", PCT, "up",
              "Utilidad / Primas retenidas", "Net income / Retained premiums",
              "Margen neto sobre la prima retenida.",
              "Net margin on retained premium."),
    RatioSpec("technical_margin", PROFITABILITY, "Resultado técnico / Primas netas devengadas", "Technical result / Net earned premiums", PCT, "up",
              "Resultado técnico / Primas devengadas", "Technical result / Earned premiums",
              "Resultado de suscripción antes de gastos de operación y resultado financiero.",
              "Underwriting result before operating expenses and financial result."),
    RatioSpec("return_on_assets", PROFITABILITY, "Utilidad neta / Activo total (ROA)", "Net income / Total assets (ROA)", PCT, "up",
              "ROA", "ROA",
              "Utilidad generada por cada peso de activo total.",
              "Profit generated per unit of total assets."),
)

BY_LABEL = {spec.label_es: spec for spec in CATALOG}
BY_CODE = {spec.code: spec for spec in CATALOG}


def format_value(value, unit, decimals=2):
    """Format a ratio for display: percentages as 12.34%, multiples as 1.23x."""
    if value is None:
        return "—"
    return f"{value * 100:.{decimals}f}%" if unit == PCT else f"{value:.{decimals}f}x"


def format_change(delta, unit, decimals=2):
    """Format a change between two ratio values: percentage points or multiples."""
    if delta is None:
        return "—"
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "►")
    body = f"{abs(delta) * 100:.{decimals}f} pp" if unit == PCT else f"{abs(delta):.{decimals}f}x"
    return f"{arrow} {body}"
