from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ParsedTransaction:
    posted_date: str  # YYYY-MM-DD
    description: str
    amount: float
    account_last4: str | None = None
    raw_line: str = ""
    external_id: str | None = None
