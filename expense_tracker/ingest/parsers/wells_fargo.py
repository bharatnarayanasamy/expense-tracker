from __future__ import annotations

import re

from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import (
    DATE_MDY,
    DATE_MDY_LOOSE,
    extract_account_last4,
    parse_amount,
    to_iso_date,
)

WELLS_LINE = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2})\s+(?P<desc>.+?)\s+(?P<amount>-?\$?\d[\d,]*\.\d{2})\s*$"
)


def _infer_year(text: str) -> int:
    m = re.search(r"\b(20\d{2})\b", text)
    if m:
        return int(m.group(1))
    from datetime import date

    return date.today().year


def parse_wells_fargo(text: str) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    lines = text.splitlines()
    year = _infer_year(text)
    txns: list[ParsedTransaction] = []

    for line in lines:
        stripped = line.strip()
        for pat in (WELLS_LINE,):
            m = pat.match(stripped)
            if m:
                iso = to_iso_date(f"{m.group('date')}/{year}")
                if not iso:
                    continue
                desc = m.group("desc").strip()
                amount = parse_amount(m.group("amount"))
                if "DEPOSIT" in desc.upper() or "PAYROLL" in desc.upper():
                    pass
                elif amount > 0:
                    amount = -abs(amount)
                txns.append(
                    ParsedTransaction(
                        posted_date=iso,
                        description=desc,
                        amount=amount,
                        raw_line=stripped,
                    )
                )
                break

    from expense_tracker.ingest.parsers.base import parse_lines_with_patterns

    if not txns:
        txns = parse_lines_with_patterns(lines, [DATE_MDY, DATE_MDY_LOOSE])

    last4 = extract_account_last4(text)
    if last4:
        for t in txns:
            t.account_last4 = last4

    if len(txns) < 3:
        warnings.append("Wells Fargo parser matched few lines.")
    return txns, warnings
