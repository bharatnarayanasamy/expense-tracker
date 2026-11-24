from __future__ import annotations

from expense_tracker.ingest.detector import Bank


def infer_account_kind(text: str, bank: Bank) -> str:
    upper = text.upper()
    if bank == Bank.CHASE_AUTO:
        return "loan"
    if any(
        k in upper
        for k in (
            "CREDIT CARD",
            "PRIME VISA",
            "WORLD OF HYATT",
            "CARDMEMBER AGREEMENT",
            "CARD MEMBER",
            " MASTERCARD",
            " VISA SIGNATURE",
            "VISA SIGNATURE",
        )
    ):
        return "credit"
    if "DEBIT CARD" in upper or "DEBIT PURCHASE" in upper:
        return "debit"
    if "CHECKING" in upper or "SAVINGS" in upper or "ADV PLUS BANKING" in upper:
        return "checking"
    if bank == Bank.CAPITAL_ONE and "CREDIT" in upper:
        return "credit"
    if "CREDIT" in upper and "CARD" in upper:
        return "credit"
    return "unknown"


def account_label(bank: str, last4: str | None, kind: str | None = None) -> str:
    kind_part = ""
    if kind and kind != "unknown":
        kind_part = f" {kind.capitalize()}"
    if last4:
        return f"{bank}{kind_part} ••{last4}"
    if kind_part:
        return f"{bank}{kind_part}".strip()
    return bank
