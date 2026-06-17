import csv as _csv
import pandas as pd


def parse_number(s: str, decimal: str = '.') -> float:
    """
    Parse a number string in Vietnamese or standard notation.

    decimal : '.' = standard (dot is decimal)
              ',' = Vietnamese (comma is decimal)

    The hint is only used for genuinely ambiguous single-separator cases:
        '1,000'  — could be 1.0 (VN) or 1000 (standard)
        '1.500'  — could be 1500 (VN) or 1.5 (standard)

    Unambiguous rules (both separator types present, or multiple of one):
        '1.500,50'   → 1500.5  (comma last → comma is decimal)
        '1,500.50'   → 1500.5  (period last → period is decimal)
        '1.234.567'  → 1234567 (multiple periods, no comma → all thousands)
        '1,234,567'  → 1234567 (multiple commas, no period  → all thousands)
        '1,5'        → 1.5     (1 digit after comma → cannot be thousands)
        '1.5'        → 1.5     (1 digit after period → cannot be thousands)
    """
    s = str(s).strip().replace(' ', '').replace('\xa0', '')
    if not s:
        raise ValueError('empty string')

    comma_count = s.count(',')
    period_count = s.count('.')

    if comma_count == 0 and period_count == 0:
        return float(s)

    # ── UNAMBIGUOUS: both separator types present ──────────────────────────
    if comma_count > 0 and period_count > 0:
        if s.rfind(',') > s.rfind('.'):
            # comma is rightmost → comma is decimal (Vietnamese)
            cleaned = s.replace('.', '').replace(',', '.')
        else:
            # period is rightmost → period is decimal (standard)
            cleaned = s.replace(',', '')
        return float(cleaned)

    # ── ONLY COMMAS present ───────────────────────────────────────────────
    if comma_count > 0:
        last_comma = s.rfind(',')
        after = s[last_comma + 1:]

        if comma_count > 1:
            # e.g. 1,234,567 → multiple commas → all are thousands
            cleaned = s.replace(',', '')
        elif len(after) == 3 and after.isdigit():
            # AMBIGUOUS: '1,000' — use hint
            if decimal == ',':
                cleaned = s.replace(',', '.')   # VN: comma is decimal → 1.0
            else:
                cleaned = s.replace(',', '')    # standard: comma is thousands → 1000
        else:
            # non-ambiguous: '1,5' / '1,50' / '1,5000' → comma is decimal
            cleaned = s.replace(',', '.')
        return float(cleaned)

    # ── ONLY PERIODS present ──────────────────────────────────────────────
    last_period = s.rfind('.')
    after = s[last_period + 1:]

    if period_count > 1:
        # e.g. 1.234.567 → multiple periods → all are thousands
        cleaned = s.replace('.', '')
    elif len(after) == 3 and after.isdigit():
        # AMBIGUOUS: '1.500' — use hint
        if decimal == ',':
            cleaned = s.replace('.', '')        # VN: period is thousands → 1500
        else:
            cleaned = s.replace(',', '')        # standard: period is decimal → 1.5
    else:
        # non-ambiguous: '1.5' / '1.50' / '1.2345' → period is decimal
        cleaned = s.replace(',', '')
    return float(cleaned)


def to_numeric_vn(series: pd.Series, decimal: str = '.') -> pd.Series:
    """Convert a string Series (possibly Vietnamese number format) to float."""
    def _safe(val):
        try:
            return parse_number(str(val), decimal=decimal)
        except (ValueError, TypeError):
            return float('nan')
    return series.apply(_safe)


def detect_csv_sep(path: str) -> str:
    """Sniff the field separator of a CSV file. Falls back to ','."""
    encodings = ['utf-8-sig', 'utf-8', 'cp1258', 'latin-1']
    sample = ''
    for enc in encodings:
        try:
            with open(path, encoding=enc, errors='replace') as f:
                sample = f.read(8192)
            break
        except OSError:
            continue

    try:
        dialect = _csv.Sniffer().sniff(sample, delimiters=',;\t|')
        return dialect.delimiter
    except _csv.Error:
        first_line = sample.split('\n')[0] if sample else ''
        counts = {d: first_line.count(d) for d in (';', ',', '\t', '|')}
        best = max(counts, key=counts.get)
        return best if counts[best] > 0 else ','
