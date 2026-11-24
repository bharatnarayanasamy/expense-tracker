from __future__ import annotations

import re
from datetime import datetime

from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import (
    DATE_MDY,
    DATE_MDY_LOOSE,
    extract_account_last4,
    parse_amount,
    parse_lines_with_patterns,
)

BOFA_LINE = re.compile(
    r"^(?P<date>\d{2}/\d{2}/\d{4})\s+(?P<desc>.+?)\s+(?P<amount>-?\$?\d[\d,]*\.\d{2})\s*$"
)
# Credit card eStatements: Trans Date Post Date Description … Amount (no year on dates)
BOFA_CC_LINE = re.compile(
    r"^(?P<trans>\d{2}/\d{2})\s+(?P<post>\d{2}/\d{2})\s+(?P<desc>.+?)\s+(?P<amount>-?[\d,]+\.\d{2})\s*$"
)


def _parse_statement_closing(text: str, filename: str = "") -> datetime | None:
    m = re.search(
        r"Statement Closing Date\s+(\d{2}/\d{2}/\d{4})",
        text,
        re.IGNORECASE,
    )
    if m:
        try:
            return datetime.strptime(m.group(1), "%m/%d/%Y")
        except ValueError:
            pass
    m = re.search(r"eStmt_(\d{4})-(\d{2})-(\d{2})", filename, re.IGNORECASE)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _year_for_credit_card_post(post_mmdd: str, closing: datetime | None, filename: str) -> int:
    if closing is not None:
        month = int(post_mmdd.split("/")[0])
        if month > closing.month:
            return closing.year - 1
        return closing.year
    m = re.search(r"eStmt_(\d{4})-\d{2}-\d{2}", filename, re.IGNORECASE)
    if m:
        return int(m.group(1))
    return datetime.today().year


def _mmdd_to_iso(mmdd: str, year: int) -> str | None:
    try:
        return datetime.strptime(f"{mmdd}/{year}", "%m/%d/%Y").date().isoformat()
    except ValueError:
        return None


def _bofa_account_last4(text: str) -> str | None:
    m = re.search(r"Account#\s+([\d\s]+)", text, re.IGNORECASE)
    if not m:
        return None
    digits = re.sub(r"\D", "", m.group(1))
    if len(digits) >= 4:
        return digits[-4:]
    return None


def _parse_bofa_credit_card_lines(
    lines: list[str], text: str, filename: str = ""
) -> list[ParsedTransaction]:
    closing = _parse_statement_closing(text, filename)
    txns: list[ParsedTransaction] = []
    for line in lines:
        stripped = line.strip()
        m = BOFA_CC_LINE.match(stripped)
        if not m:
            continue
        desc = m.group("desc").strip()
        up = desc.upper()
        if up.startswith("INTEREST CHARGED") or up.startswith("TOTAL "):
            continue
        post = m.group("post")
        year = _year_for_credit_card_post(post, closing, filename)
        iso = _mmdd_to_iso(post, year)
        if not iso:
            continue
        amount = parse_amount(m.group("amount"))
        if amount == 0:
            continue
        txns.append(
            ParsedTransaction(
                posted_date=iso,
                description=desc,
                amount=amount,
                raw_line=stripped,
            )
        )
    return txns


def _normalize_bofa_checking_amount(description: str, amount: float) -> float:
    """Checking eStatements: deposits are +, withdrawals are − in the PDF."""
    up = description.upper()
    if amount < 0:
        return amount
    if any(k in up for k in ("CHECKCARD", "PURCHASE", "WITHDRWL", "PMNT SENT", "FEE", "ATM")):
        return -abs(amount)
    return amount


def _normalize_bofa_credit_card_amount(description: str, amount: float) -> float:
    """Credit card eStatements: purchases are +, credits/payments are − in the PDF."""
    up = description.upper()
    if amount <= 0:
        return amount
    if "RECURRING FROM CHK" in up or "PAYMENT FROM CHK" in up:
        return amount
    if any(k in up for k in ("REFUND", "CASHBACK", "CREDIT")):
        return amount
    return -abs(amount)


def parse_bofa(text: str, filename: str = "") -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    lines = text.splitlines()
    checking_txns = parse_lines_with_patterns(lines, [DATE_MDY, DATE_MDY_LOOSE])
    cc_txns = _parse_bofa_credit_card_lines(lines, text, filename)
    is_credit_card = len(cc_txns) > len(checking_txns)
    txns = cc_txns if is_credit_card else checking_txns

    last4 = _bofa_account_last4(text) or extract_account_last4(text)
    if last4:
        for t in txns:
            t.account_last4 = last4

    skip_prefixes = ("BEGINNING BALANCE", "ENDING BALANCE", "TOTAL ", "DATE ")
    filtered: list[ParsedTransaction] = []
    for t in txns:
        up = t.description.upper()
        if any(up.startswith(p) for p in skip_prefixes):
            continue
        if is_credit_card:
            t.amount = _normalize_bofa_credit_card_amount(t.description, t.amount)
        else:
            t.amount = _normalize_bofa_checking_amount(t.description, t.amount)
        filtered.append(t)

    if len(filtered) < 3:
        warnings.append("Bank of America parser matched few lines.")
    return filtered, warnings
