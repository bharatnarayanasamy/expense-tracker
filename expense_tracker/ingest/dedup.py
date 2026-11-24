from __future__ import annotations

import hashlib
import re


def normalize_description(description: str) -> str:
    s = description.upper().strip()
    s = re.sub(r"\s+", " ", s)
    return s


def make_dedup_key(
    bank: str,
    posted_date: str,
    amount: float,
    description: str,
    account_last4: str | None = None,
    external_id: str | None = None,
) -> str:
    if external_id:
        payload = f"{bank}|{external_id.strip()}"
    else:
        payload = "|".join(
            [
                bank,
                account_last4 or "",
                posted_date,
                f"{amount:.2f}",
                normalize_description(description),
            ]
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
