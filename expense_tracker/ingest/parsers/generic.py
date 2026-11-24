from __future__ import annotations

from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import (
    DATE_MDY,
    DATE_MDY_LOOSE,
    extract_account_last4,
    parse_lines_with_patterns,
)


def parse_generic(text: str) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    lines = text.splitlines()
    txns = parse_lines_with_patterns(lines, [DATE_MDY, DATE_MDY_LOOSE])
    last4 = extract_account_last4(text)
    if last4:
        for t in txns:
            t.account_last4 = last4
    if len(txns) < 3:
        warnings.append(
            "Generic parser found few transactions; statement layout may need a bank-specific parser."
        )
    return txns, warnings
