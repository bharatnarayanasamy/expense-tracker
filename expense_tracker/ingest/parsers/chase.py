from __future__ import annotations

import re

from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import (
    DATE_MDY,
    DATE_MDY_LOOSE,
    extract_account_last4,
    parse_amount,
    parse_lines_with_patterns,
    to_iso_date,
)

# Chase credit: MM/DD  description  amount (sometimes without year on line — infer from statement)
CHASE_SHORT = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<rest>.+?)\s+(?P<amount>-?\$?\d{1,3}(?:,\d{3})*\.\d{2})\s*$"
)


def _infer_year(text: str) -> int:
    m = re.search(r"(?:Statement Period|Opening/closing date).*?(\d{4})", text, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"\b(20\d{2})\b", text)
    if m:
        return int(m.group(1))
    from datetime import date

    return date.today().year


def parse_chase(text: str) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    lines = text.splitlines()
    year = _infer_year(text)
    txns = parse_lines_with_patterns(lines, [DATE_MDY, DATE_MDY_LOOSE])

    if len(txns) < 5:
        for line in lines:
            m = CHASE_SHORT.match(line.strip())
            if not m:
                continue
            md = m.group("date")
            iso = to_iso_date(f"{md}/{year}")
            if not iso:
                continue
            desc = m.group("rest").strip()
            if "PAYMENT" in desc.upper() and "THANK" in desc.upper():
                amount = parse_amount(m.group("amount"))
            else:
                amount = parse_amount(m.group("amount"))
                if amount > 0 and "PAYMENT" not in desc.upper():
                    amount = -abs(amount)
            if desc.upper().startswith("TRANSACTION"):
                continue
            txns.append(
                ParsedTransaction(
                    posted_date=iso,
                    description=desc,
                    amount=amount if amount <= 0 else -abs(amount),
                    raw_line=line.strip(),
                )
            )

    last4 = extract_account_last4(text)
    if last4:
        for t in txns:
            t.account_last4 = last4

    # Credit card purchases are outflows
    for t in txns:
        if t.amount > 0 and "PAYMENT" not in t.description.upper():
            if "REFUND" not in t.description.upper():
                t.amount = -abs(t.amount)

    if len(txns) < 3:
        warnings.append("Chase parser matched few lines; falling back may be needed.")
    return txns, warnings
