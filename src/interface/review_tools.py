"""Helpers for reviewing extracted financial statement rows."""
import pandas as pd
from src.normalization.normalizer import canonicalize
from src.normalization.mappings import ALL_MAPPINGS
from src.normalization.insurance_2025_aliases import INSURANCE_ALIASES

CANONICAL_KEYS = sorted(set(ALL_MAPPINGS) | set(INSURANCE_ALIASES))


def rows_for_review(raw):
    return pd.DataFrame([
        {"Source label": str(row.get("label", "")),
         "Amount": float(row["value"]),
         "Canonical key": canonicalize(row.get("label", "")) or "",
         "Location": str(row.get("source_location", "")),
         "Include": bool(canonicalize(row.get("label", "")))}
        for row in raw if row.get("value") is not None
    ], columns=["Source label", "Amount", "Canonical key", "Location", "Include"])


def reviewed_values(frame):
    values, origins = {}, {}
    for index, row in frame.iterrows():
        if not bool(row.get("Include", False)):
            continue
        key = str(row.get("Canonical key", "")).strip()
        if not key:
            raise ValueError(f"Included row {index + 1} has no canonical key")
        if key not in CANONICAL_KEYS:
            raise ValueError(f"Unknown canonical key: {key}")
        amount = row.get("Amount")
        if pd.isna(amount):
            raise ValueError(f"Missing amount for {key}")
        if key in values:
            raise ValueError(f"Duplicate key '{key}' at {origins[key]} and row {index + 1}")
        values[key] = float(amount)
        origins[key] = index + 1
    return values


def reconcile(data):
    checks = []
    for label, total, parts in [
        ("Assets = liabilities + equity", "total_assets", ["total_liabilities", "total_equity"]),
        ("Written = retained + ceded premiums", "gross_premiums_written", ["retained_premiums", "ceded_premiums"]),
    ]:
        if total in data and all(p in data for p in parts):
            difference = data[total] - sum(data[p] for p in parts)
            tolerance = max(1.0, abs(data[total]) * 1e-7)
            checks.append({"Check": label, "Difference": difference, "Status": "OK" if abs(difference) <= tolerance else "Review"})
    return checks
