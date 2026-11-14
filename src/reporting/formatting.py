"""Display formatting shared by the dashboard, insights and exports."""


def money(value, lang="es", decimals=2):
    """Compact peso amount: 45_794_113_929.98 -> '$45.79 mil millones' (es) / 'MXN 45.79 bn' (en)."""
    if value is None:
        return "—"
    sign = "-" if value < 0 else ""
    v = abs(value)
    if lang == "es":
        if v >= 1e9:
            return f"{sign}${v / 1e9:,.{decimals}f} mil millones"
        if v >= 1e6:
            return f"{sign}${v / 1e6:,.1f} millones"
        return f"{sign}${v:,.0f}"
    if v >= 1e9:
        return f"{sign}MXN {v / 1e9:,.{decimals}f} bn"
    if v >= 1e6:
        return f"{sign}MXN {v / 1e6:,.1f} M"
    return f"{sign}MXN {v:,.0f}"


def money_short(value):
    """Very compact amount for chart labels, in billions of pesos: 45.8 mil M."""
    if value is None:
        return "—"
    return f"{value / 1e9:,.1f}"


def pct(value, decimals=1, signed=False):
    if value is None:
        return "—"
    return f"{value * 100:+.{decimals}f}%" if signed else f"{value * 100:.{decimals}f}%"


def pp(delta, decimals=1):
    if delta is None:
        return "—"
    return f"{delta * 100:+.{decimals}f} pp"


def join_years(years, lang="es"):
    years = [str(y) for y in years]
    if not years:
        return ""
    if len(years) == 1:
        return years[0]
    conj = "y" if lang == "es" else "and"
    return ", ".join(years[:-1]) + f" {conj} {years[-1]}"
