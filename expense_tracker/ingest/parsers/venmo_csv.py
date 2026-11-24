from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from expense_tracker.ingest.models import ParsedTransaction

VENMO_HEADER = re.compile(r"^,?ID,Datetime,Type,", re.IGNORECASE)
ACCOUNT_HANDLE = re.compile(r"@([A-Za-z0-9_-]+)")


def _parse_venmo_amount(raw: str) -> float | None:
    s = raw.strip()
    if not s:
        return None
    s = s.replace("$", "").replace(",", "").strip()
    if s.startswith("+"):
        return float(s[1:].strip())
    if s.startswith("-"):
        return -float(s[1:].strip())
    try:
        return float(s)
    except ValueError:
        return None


def _parse_venmo_datetime(raw: str) -> str | None:
    s = raw.strip()
    if not s:
        return None
    try:
        if "T" in s:
            return datetime.fromisoformat(s).date().isoformat()
        return datetime.strptime(s, "%Y-%m-%d").date().isoformat()
    except ValueError:
        return None


def _extract_account_handle(text: str) -> str | None:
    m = ACCOUNT_HANDLE.search(text)
    return m.group(1) if m else None


def _build_description(
    txn_type: str,
    note: str,
    from_user: str,
    to_user: str,
    destination: str,
) -> str:
    note = note.strip()
    if note:
        return f"Venmo: {note}"
    dest = destination.strip()
    if txn_type == "Merchant Transaction" and dest:
        return f"Venmo: {dest}"
    other = to_user.strip() or from_user.strip()
    if other:
        return f"Venmo {txn_type}: {other}"
    return f"Venmo {txn_type}"


def parse_venmo_csv(csv_text: str) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    lines = csv_text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if VENMO_HEADER.match(line):
            header_idx = i
            break
    if header_idx is None:
        warnings.append("Venmo CSV: could not find transaction header row.")
        return [], warnings

    handle = _extract_account_handle("\n".join(lines[:3]))
    reader = csv.DictReader(lines[header_idx:])
    txns: list[ParsedTransaction] = []
    for row in reader:
        venmo_id = (row.get("ID") or "").strip()
        if not venmo_id:
            continue
        posted = _parse_venmo_datetime(row.get("Datetime") or "")
        amount = _parse_venmo_amount(row.get("Amount (total)") or "")
        if posted is None or amount is None or amount == 0:
            continue
        status = (row.get("Status") or "").strip()
        if status and status not in ("Complete", "Refunded"):
            continue
        txn_type = (row.get("Type") or "").strip() or "Transaction"
        desc = _build_description(
            txn_type,
            row.get("Note") or "",
            row.get("From") or "",
            row.get("To") or "",
            row.get("Destination") or "",
        )
        last4 = handle[-4:] if handle and len(handle) >= 4 else handle
        txns.append(
            ParsedTransaction(
                posted_date=posted,
                description=desc,
                amount=amount,
                raw_line=f"{venmo_id}|{desc}|{amount}",
                account_last4=last4,
                external_id=venmo_id,
            )
        )

    if not txns:
        warnings.append("Venmo CSV: no transactions parsed.")
    elif not handle:
        warnings.append("Venmo CSV: could not read @username from header.")
    return txns, warnings
