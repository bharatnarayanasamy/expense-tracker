from __future__ import annotations

from enum import Enum


class Bank(str, Enum):
    CHASE = "Chase"
    CHASE_AUTO = "Chase Auto"
    BOFA = "Bank of America"
    WELLS_FARGO = "Wells Fargo"
    CAPITAL_ONE = "Capital One"
    UNKNOWN = "Unknown"


def detect_bank(text: str) -> Bank:
    upper = text.upper()
    compact = upper.replace(" ", "")
    if (
        "CHASEAUTO" in compact
        or "AUTO LOANPAYMENT" in compact
        or "CHASE AUTO FINANCE" in upper
        or "VEHICLEDESCRIPTION" in compact
    ):
        return Bank.CHASE_AUTO
    if (
        "JPMORGAN CHASE" in upper
        or "CHASE CARD" in upper
        or "CHASE.COM" in upper
        or "WWW.CHASE.COM" in upper
        or "PRIME VISA" in upper
        or "\nCHASE\n" in upper
    ):
        return Bank.CHASE
    if "BANK OF AMERICA" in upper or "BANKOFAMERICA" in upper.replace(" ", ""):
        return Bank.BOFA
    if "WELLS FARGO" in upper:
        return Bank.WELLS_FARGO
    if "CAPITAL ONE" in upper:
        return Bank.CAPITAL_ONE
    return Bank.UNKNOWN
