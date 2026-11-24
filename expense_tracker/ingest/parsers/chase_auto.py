from __future__ import annotations

import re

from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import parse_amount, to_iso_date

# Smushed PDF text: D09a/t2e5/26 ... PAYMENT-THANKYOU ... Total ($659.06)
AUTO_PAYMENT = re.compile(
    r"(?P<mdy>\d{2}/\d{2}/\d{2}).{0,120}?PAYMENT.{0,40}?THANKYOU.{0,80}?"
    r"Total\s*\(\$(?P<amt>[\d,]+\.\d{2})\)",
    re.IGNORECASE | re.DOTALL,
)
DUE_LINE = re.compile(
    r"(?P<mdy>\d{2}/\d{2}/\d{2})\s+\$(?P<amt>[\d,]+\.\d{2})"
)


def _mdy_to_iso(mdy: str) -> str | None:
    return to_iso_date(mdy) or to_iso_date(f"{mdy[:6]}20{mdy[-2:]}")


def parse_chase_auto(text: str) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    txns: list[ParsedTransaction] = []
    flat = text.replace("\n", " ")

    for m in AUTO_PAYMENT.finditer(flat):
        iso = _mdy_to_iso(m.group("mdy"))
        if not iso:
            continue
        amt = parse_amount(m.group("amt"))
        txns.append(
            ParsedTransaction(
                posted_date=iso,
                description="Chase Auto loan payment",
                amount=-abs(amt),
                raw_line=m.group(0)[:200],
            )
        )

    if not txns:
        for m in DUE_LINE.finditer(text):
            iso = _mdy_to_iso(m.group("mdy"))
            if not iso:
                continue
            amt = parse_amount(m.group("amt"))
            txns.append(
                ParsedTransaction(
                    posted_date=iso,
                    description="Chase Auto scheduled payment due",
                    amount=-abs(amt),
                    raw_line=m.group(0),
                )
            )
        if len(txns) > 1:
            txns = txns[:1]
            warnings.append("Chase Auto: used payment due line only (no activity detail found).")

    if not txns:
        warnings.append("Chase Auto parser matched no payment lines.")
    return txns, warnings
