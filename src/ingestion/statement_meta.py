"""Detect what a statement file is (balance sheet or income statement), its fiscal year and entity.

Detection reads the document header (PDF first page, or the first cells of a sheet) and falls back to the
file name. This lets the application accept a folder or a bulk upload of statements without asking the
user to label each file.
"""
import re
from dataclasses import dataclass
from pathlib import Path

BALANCE, INCOME = "balance", "income"

_BALANCE_RE = re.compile(r"balance\s+general|balance\s+sheet|estado\s+de\s+situaci[oó]n\s+financiera", re.I)
_INCOME_RE = re.compile(r"estado\s+de\s+resultados|income\s+statement|profit\s+(and|&)\s+loss", re.I)
_YEAR_RE = re.compile(r"(?<!\d)(20\d{2}|19\d{2})(?!\d)")
_HEADER_YEAR_RE = re.compile(r"(?:\bde|\bof|\bat|\bal)\s+(20\d{2}|19\d{2})\b", re.I)


@dataclass
class StatementMeta:
    path: str
    kind: str | None
    year: int | None
    entity: str | None = None
    source: str = "filename"  # "header" when read from the document itself

    def to_dict(self):
        return {"path": self.path, "kind": self.kind, "year": self.year, "entity": self.entity, "source": self.source}


def _header_text(path):
    """Return the first lines of a document as plain text, or '' when unavailable."""
    suffix = Path(path).suffix.lower()
    try:
        if suffix == ".pdf":
            import pdfplumber
            with pdfplumber.open(path) as pdf:
                return "\n".join((pdf.pages[0].extract_text() or "").splitlines()[:8])
        if suffix in {".xlsx", ".xlsm", ".xls"}:
            import pandas as pd
            frame = pd.read_excel(path, header=None, nrows=8, dtype=object)
            return "\n".join(" ".join(str(v) for v in row if str(v) != "nan") for row in frame.values.tolist())
        if suffix == ".csv":
            with open(path, encoding="utf-8-sig", errors="ignore") as handle:
                return "".join(handle.readline() for _ in range(8))
    except Exception:
        return ""
    return ""


def detect_statement(path):
    """Classify a statement file. Header evidence wins over the file name."""
    path = str(path)
    name = Path(path).stem.replace("_", " ").replace("-", " ")
    text = _header_text(path)
    kind = year = entity = None
    source = "filename"
    if text:
        # Check the title lines; "ESTADO DE RESULTADOS" must be tested first because income statements
        # can mention "balance" in prose, while balance sheets rarely contain the income title.
        if _INCOME_RE.search(text):
            kind, source = INCOME, "header"
        elif _BALANCE_RE.search(text):
            kind, source = BALANCE, "header"
        matches = _HEADER_YEAR_RE.findall(text) or _YEAR_RE.findall(text)
        if matches:
            year = int(matches[-1])
        first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
        if first and not (_BALANCE_RE.search(first) or _INCOME_RE.search(first)):
            entity = first
    if kind is None:
        if _INCOME_RE.search(name) or re.search(r"resultados|income|p&l", name, re.I):
            kind = INCOME
        elif _BALANCE_RE.search(name) or re.search(r"balance", name, re.I):
            kind = BALANCE
    if year is None:
        found = _YEAR_RE.findall(name)
        year = int(found[-1]) if found else None
    return StatementMeta(path=path, kind=kind, year=year, entity=entity, source=source)
