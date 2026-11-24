from __future__ import annotations

import re
from datetime import datetime

from expense_tracker.ingest.models import ParsedTransaction

DATE_MDY = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<rest>.+?)\s+(?P<amount>-?\$?\d{1,3}(?:,\d{3})*\.\d{2}-?)\s*$"
)
DATE_MDY_LOOSE = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<rest>.+)\s+(?P<amount>-?\$?\d[\d,]*\.\d{2}-?)\s*$"
)
AMOUNT_ONLY = re.compile(r"(?P<amount>-?\$?\d{1,3}(?:,\d{3})*\.\d{2}-?)")


def parse_amount(raw: str) -> float:
    s = raw.strip().replace("$", "").replace(",", "")
    if s.endswith("-"):
        s = "-" + s[:-1]
    return float(s)


def to_iso_date(mdy: str) -> str | None:
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(mdy, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_lines_with_patterns(
    lines: list[str],
    patterns: list[re.Pattern[str]],
) -> list[ParsedTransaction]:
    results: list[ParsedTransaction] = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 10:
            continue
        matched = False
        for pat in patterns:
            m = pat.match(line)
            if not m:
                continue
            iso = to_iso_date(m.group("date"))
            if not iso:
                continue
            desc = m.group("rest").strip()
            amount = parse_amount(m.group("amount"))
            if desc.upper().startswith("DATE") and "DESCRIPTION" in desc.upper():
                continue
            results.append(
                ParsedTransaction(
                    posted_date=iso,
                    description=desc,
                    amount=amount,
                    raw_line=line,
                )
            )
            matched = True
            break
        if matched:
            continue
    return results


def extract_account_last4(text: str) -> str | None:
    patterns = [
        r"Account Number:\s*(?:X{4}\s+){2,3}(\d{4})",
        r"(?:Account|Acct|Card)\s*(?:Number|#)?\s*(?:X{4}\s+){0,3}(\d{4})",
        r"(?:Account|Acct|Card)\s*(?:Number|#)?\s*[Xx*\.]{4,}(\d{4})",
        r"\b(?:X{4}|\*{4})\s*(\d{4})\b",
        r"ending in\s*(\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None
