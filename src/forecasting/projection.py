"""12-month projections.

``project_reference`` reproduces, step by step, the method used in the reference workbook
(PIA_AnálisisFinanciero.xlsx, sheets PROYECCIÓN_VENTAS and SINIESTRALIDAD):

1. Year-over-year variation of the series.
2. Arithmetic mean of those variations (g).
3. Monthly rate = g / 12.
4. Monthly base = last fiscal-year amount / 12.
5. Month k = month k-1 * (1 + monthly rate), starting from the monthly base.
6. Projected total = sum of the 12 months.

``project_scenarios`` adds alternative annual methods so the result of the reference method can be
compared. They are complementary estimates, not replacements: with only five annual observations any
statistical method is indicative, and none of them models seasonality, pricing changes or the macro
environment.
"""
from dataclasses import dataclass, field


@dataclass
class MonthlyPoint:
    month: int
    value: float
    rate: float
    cumulative_vs_base: float

    def to_dict(self):
        return {"month": self.month, "value": self.value, "rate": self.rate,
                "cumulative_vs_base": self.cumulative_vs_base}


@dataclass
class ReferenceProjection:
    years: list
    values: list
    yoy: list                      # same length as values; first item is None
    mean_growth: float             # g (arithmetic mean of yoy)
    monthly_rate: float            # g / 12
    monthly_base: float            # last value / 12
    months: list = field(default_factory=list)
    total: float = 0.0
    total_growth: float = 0.0      # total / last value - 1
    horizon_year: int | None = None

    def to_dict(self):
        return {"years": self.years, "values": self.values, "yoy": self.yoy,
                "mean_growth": self.mean_growth, "monthly_rate": self.monthly_rate,
                "monthly_base": self.monthly_base, "months": [m.to_dict() for m in self.months],
                "total": self.total, "total_growth": self.total_growth, "horizon_year": self.horizon_year}


@dataclass
class Scenario:
    key: str
    name: str
    total: float
    growth: float                  # total / last value - 1
    description: str

    def to_dict(self):
        return {"key": self.key, "name": self.name, "total": self.total,
                "growth": self.growth, "description": self.description}


def yoy_growth(values):
    """Year-over-year variation; the first element is None."""
    out = [None]
    for prev, cur in zip(values, values[1:]):
        out.append(None if prev in (None, 0) or cur is None else cur / prev - 1)
    return out


def _clean(years, values):
    pairs = [(y, v) for y, v in zip(years, values) if v is not None]
    if len(pairs) < 2:
        raise ValueError("At least two fiscal years with data are required to project.")
    pairs.sort()
    return [p[0] for p in pairs], [float(p[1]) for p in pairs]


def project_reference(years, values, horizon=12):
    """Reference-workbook method (see module docstring)."""
    years, values = _clean(years, values)
    yoy = yoy_growth(values)
    rates = [g for g in yoy if g is not None]
    mean_growth = sum(rates) / len(rates)
    monthly_rate = mean_growth / 12
    monthly_base = values[-1] / 12
    months, previous = [], monthly_base
    for k in range(1, horizon + 1):
        current = previous * (1 + monthly_rate)
        months.append(MonthlyPoint(k, current, monthly_rate, current / monthly_base - 1))
        previous = current
    total = sum(m.value for m in months)
    return ReferenceProjection(years=years, values=values, yoy=yoy, mean_growth=mean_growth,
                               monthly_rate=monthly_rate, monthly_base=monthly_base, months=months,
                               total=total, total_growth=total / values[-1] - 1, horizon_year=years[-1] + 1)


def project_scenarios(years, values):
    """Alternative annual estimates for the year following the last observation."""
    years, values = _clean(years, values)
    n, last = len(values), values[-1]
    yoy = [g for g in yoy_growth(values) if g is not None]
    mean_g = sum(yoy) / len(yoy)
    cagr = (values[-1] / values[0]) ** (1 / (n - 1)) - 1 if values[0] > 0 and values[-1] > 0 else mean_g
    # Ordinary least squares on t = 0..n-1.
    t_mean, y_mean = (n - 1) / 2, sum(values) / n
    slope = sum((t - t_mean) * (v - y_mean) for t, v in enumerate(values)) / sum((t - t_mean) ** 2 for t in range(n))
    linear = y_mean + slope * (n - t_mean)
    ref = project_reference(years, values)
    scenarios = [
        Scenario("reference", "Método del Excel (mensualizado)", ref.total, ref.total_growth,
                 "Promedio aritmético del crecimiento anual dividido entre 12 y aplicado mes a mes sobre el promedio mensual del último año."),
        Scenario("annual_mean", "Crecimiento promedio anual", last * (1 + mean_g), mean_g,
                 "Último año × (1 + promedio aritmético de las variaciones anuales)."),
        Scenario("cagr", "Crecimiento compuesto (CAGR)", last * (1 + cagr), cagr,
                 "Último año × (1 + tasa compuesta de crecimiento entre el primer y el último año)."),
        Scenario("linear", "Tendencia lineal (MCO)", linear, linear / last - 1,
                 "Recta de mínimos cuadrados ajustada a los años observados, extrapolada un año."),
    ]
    return scenarios
