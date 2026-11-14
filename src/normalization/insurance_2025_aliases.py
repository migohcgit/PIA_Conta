"""Additional labels used in Mexican (CNSF format) consolidated insurance statements, 2021-2025."""

INSURANCE_ALIASES = {
    "course_risk_reserves": ["de riesgos en curso"],
    "investment_income": ["de inversiones"],
    "technical_reserves_change": ["incremento neto de la reserva de riesgos en curso y de fianzas en vigor"],
    "accounts_receivable": ["deudores"],
    "reinsurance_assets": ["reaseguradores y reafianzadores neto"],
    "accounts_payable": ["acreedores"],
    "reinsurance_liabilities": ["reaseguradores y reafianzadores"],
    "capital_reserve": ["legal"],
    "retained_earnings": ["resultados o remanente de ejercicios anteriores"],
    "operating_income": ["utilidad perdida de la operacion"],
    "property_plant_equipment": ["inmuebles neto"],
    "cash_and_equivalents": ["caja y bancos"],
    # 2021-2022 statements use "Disponibilidad" for what later years call "Efectivo y Equivalentes de Efectivo".
    "available_assets": ["disponibilidad"],
    # Income-statement subtotals used to verify that each statement foots arithmetically.
    "other_technical_reserves_change": ["incremento neto de otras reservas tecnicas"],
    "analogous_operations_result": ["resultado de operaciones analogas y conexas"],
    "gross_profit": ["utilidad perdida bruta"],
    "pre_tax_income": ["utilidad perdida antes de impuestos a la utilidad"],
    "income_tax": ["provision para el pago de impuestos a la utilidad"],
    "total_liabilities_and_equity": ["suma del pasivo y capital"],
}
