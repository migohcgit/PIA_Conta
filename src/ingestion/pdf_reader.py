#Coordinate PDF extraction for one- and two-column financial statements
import re
import pdfplumber
from .common import parse_number

# An amount token: optional parentheses/sign/currency, digits with thousands separators and optional decimals.
_AMOUNT_TOKEN = re.compile(r"^\(?-?[$€£]?\d[\d,]*(?:\.\d+)?\)?$")
_BARE_YEAR = re.compile(r"^(19|20)\d{2}$")
# Title/period lines ("DEL 1 DE ENERO AL 31 DE DICIEMBRE DE 2025") carry day numbers that are not amounts.
_PERIOD_LINE = re.compile(r"\b(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", re.IGNORECASE)
# Footer lines such as "Ciudad de México, a 24 de febrero de 2026" are not financial line items.
_FOOTER = re.compile(r"^(ciudad|cdmx|monterrey)\b.*\b(de|del)\s+\d{4}$|\ba\s+\d{1,2}\s+de\s+\w+\s+de\b|^(ciudad|cdmx|monterrey)\b.*,\s*a$", re.IGNORECASE)


def _line_to_item(text, location):
    """Split a text line into (label, amount).

    The amount is the FIRST numeric token after the label. Some statements carry extra
    trailing figures on the same line (for example a stray ``0.00`` in a far-right column
    or a prior-year column); taking the last number would then corrupt the label and drop
    the real amount.
    """
    text = " ".join(text.split()).strip()
    if _FOOTER.search(text) or _PERIOD_LINE.search(text):
        return None
    tokens = text.split(" ")
    for i, token in enumerate(tokens):
        if i == 0 or not _AMOUNT_TOKEN.match(token):
            continue
        # A bare four-digit year ("... ejercicio de 2025") is narrative text, not an amount. Real amounts in these
        # statements carry thousands separators and/or decimals.
        if _BARE_YEAR.match(token):
            return None
        label = " ".join(tokens[:i]).strip(" .:-")
        value = parse_number(token)
        if not label or value is None or _FOOTER.search(label):
            return None
        return {"label": label, "value": value, "source_location": location}
    return None


def _group_rows(words, page_width):
    """Group words into visual rows by vertical centre.

    Label and amount of one row can differ by a fraction of a point when the PDF mixes fonts, so grouping by
    an exact ``top`` coordinate splits rows in two and silently drops them. The tolerance scales with the
    page size (statements are sometimes exported at several times the standard 612 pt width) and stays far
    below half the row pitch, so neighbouring rows are never merged.
    """
    tolerance = 3.0 * (float(page_width) / 612.0)
    centered = sorted(words, key=lambda w: (float(w["top"]) + float(w["bottom"])) / 2)
    rows, current, anchor = [], [], None
    for word in centered:
        centre = (float(word["top"]) + float(word["bottom"])) / 2
        if anchor is None or abs(centre - anchor) <= tolerance:
            current.append(word)
            anchor = centre if anchor is None else sum((float(w["top"]) + float(w["bottom"])) / 2 for w in current) / len(current)
        else:
            rows.append(current)
            current, anchor = [word], centre
    if current:
        rows.append(current)
    return rows


def read_pdf(path):

    lines = []
    with pdfplumber.open(path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            words = page.extract_words(x_tolerance=2, y_tolerance=3, keep_blank_chars=False)
            if words:
                rows = dict(enumerate(_group_rows(words, page.width)))
                # A two-column balance sheet commonly has its first amount around
                # 38% of page width and its second around 90%. Income statements often
                # have only one amount column near 70-90% of page width.
                numeric_word = re.compile(r"^\(?-?[$€£]?\d[\d,.]*\)?$")
                left_amount_count = sum(
                    1 for row in rows.values() for w in row
                    if page.width * 0.25 <= float(w["x0"]) <= page.width * 0.48
                    and numeric_word.match(w["text"].replace(" ", ""))
                )
                has_left_amount = left_amount_count >= 3
                for row_idx, row_words in enumerate(rows.values(), start=1):
                    if not has_left_amount:
                        text = " ".join(w["text"] for w in sorted(row_words, key=lambda x: x["x0"]))
                        item = _line_to_item(text, f"page:{page_num},line:{row_idx}")
                        if item:
                            lines.append(item)
                        continue
                    split_x = page.width * 0.455
                    left = [w for w in row_words if float(w["x0"]) < split_x]
                    right = [w for w in row_words if float(w["x0"]) >= split_x]
                    for side_name, side_words in (("left", left), ("right", right)):
                        if not side_words:
                            continue
                        text = " ".join(w["text"] for w in sorted(side_words, key=lambda x: x["x0"]))
                        item = _line_to_item(text, f"page:{page_num},line:{row_idx},{side_name}")
                        if item:
                            lines.append(item)
                if lines:
                    continue
            # Fallback for PDFs whose word coordinates are unavailable.
            text = page.extract_text() or ""
            for row_idx, line in enumerate(text.splitlines(), start=1):
                item = _line_to_item(line, f"page:{page_num},line:{row_idx}")
                if item:
                    lines.append(item)
    if not lines:
        raise ValueError("No financial line items could be extracted. The PDF may be scanned or its layout may not be supported.")
    return lines
