from __future__ import annotations

import io
import re
from datetime import datetime

import pdfplumber

from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import (
    DATE_MDY,
    DATE_MDY_LOOSE,
    extract_account_last4,
    parse_amount,
    parse_lines_with_patterns,
    to_iso_date,
)

CAP_ONE = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<desc>.+?)\s+(?P<amount>-?\$?\d[\d,]*\.\d{2})\s*$"
)

CAP_ONE_TABLE_ROW = re.compile(
    r"^(?P<m1>[A-Za-z]{3})\s+(?P<d1>\d{1,2})\s+(?P<m2>[A-Za-z]{3})\s+(?P<d2>\d{1,2})\s+"
    r"(?P<desc>.+?)\s+(?:(?P<credit>-)\s*)?\$(?P<amt>[\d,]+\.\d{2})\s*$"
)

MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _infer_year(text: str, filename: str = "") -> int:
    m = re.search(r"Statement_(\d{2})(\d{4})", filename, re.IGNORECASE)
    if m:
        return int(m.group(2))
    m = re.search(r"\b(20\d{2})\b", text)
    if m:
        return int(m.group(1))
    return datetime.today().year


def _month_day_to_iso(month: str, day: str, year: int) -> str | None:
    key = month[:3].lower()
    if key not in MONTHS:
        return None
    return f"{year}-{MONTHS[key]:02d}-{int(day):02d}"


def _parse_cap_one_line(line: str, year: int) -> ParsedTransaction | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("Trans Date"):
        return None
    upper = stripped.upper()
    if upper.startswith(("EUR", "EXCHANGE", "TK#", "ORIG:", "PSGR:", "TOTAL ")):
        return None
    m = CAP_ONE_TABLE_ROW.match(stripped)
    if not m:
        return None
    iso = _month_day_to_iso(m.group("m2"), m.group("d2"), year)
    if not iso:
        return None
    desc = m.group("desc").strip()
    amt = parse_amount(m.group("amt"))
    if m.group("credit") == "-" or "AUTOPAY" in desc.upper() or "PAYMENT" in desc.upper():
        amount = -abs(amt)
    else:
        amount = -abs(amt) if amt > 0 else amt
    return ParsedTransaction(
        posted_date=iso,
        description=desc,
        amount=amount,
        raw_line=stripped,
    )


def parse_capital_one_from_pdf(
    pdf_bytes: bytes, text: str, filename: str = ""
) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    year = _infer_year(text, filename)
    txns: list[ParsedTransaction] = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables() or []:
                for row in table:
                    for cell in row:
                        if cell is None:
                            continue
                        cell_text = str(cell)
                        if "Trans Date" not in cell_text and "Post Date" not in cell_text:
                            continue
                        for line in cell_text.split("\n"):
                            parsed = _parse_cap_one_line(line, year)
                            if parsed:
                                txns.append(parsed)

    last4 = extract_account_last4(text)
    if not last4:
        m = re.search(r"#(\d{4})\b", text)
        if m:
            last4 = m.group(1)
    if last4:
        for t in txns:
            t.account_last4 = last4

    if len(txns) < 3:
        warnings.append("Capital One table parser matched few rows; tried text fallback.")
        txns, w2 = parse_capital_one(text, filename)
        warnings.extend(w2)
    return txns, warnings


def parse_capital_one(text: str, filename: str = "") -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    lines = text.splitlines()
    year = _infer_year(text, filename)
    txns: list[ParsedTransaction] = []

    for line in lines:
        parsed = _parse_cap_one_line(line, year)
        if parsed:
            txns.append(parsed)
            continue
        stripped = line.strip()
        m = CAP_ONE.match(stripped)
        if not m:
            continue
        iso = to_iso_date(f"{m.group('date')}/{year}")
        if not iso:
            continue
        desc = m.group("desc").strip()
        amount = parse_amount(m.group("amount"))
        if "PAYMENT" not in desc.upper() and amount > 0:
            amount = -abs(amount)
        txns.append(
            ParsedTransaction(
                posted_date=iso,
                description=desc,
                amount=amount,
                raw_line=stripped,
            )
        )

    if not txns:
        txns = parse_lines_with_patterns(lines, [DATE_MDY, DATE_MDY_LOOSE])

    last4 = extract_account_last4(text)
    if last4:
        for t in txns:
            t.account_last4 = last4

    if len(txns) < 3:
        warnings.append("Capital One parser matched few lines.")
    return txns, warnings
