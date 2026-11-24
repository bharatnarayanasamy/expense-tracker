from expense_tracker.ingest.detector import Bank
from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.bofa import parse_bofa
from expense_tracker.ingest.parsers.capital_one import (
    parse_capital_one,
    parse_capital_one_from_pdf,
)
from expense_tracker.ingest.parsers.chase import parse_chase
from expense_tracker.ingest.parsers.chase_auto import parse_chase_auto
from expense_tracker.ingest.parsers.generic import parse_generic
from expense_tracker.ingest.parsers.wells_fargo import parse_wells_fargo


def parse_statement(
    bank: Bank,
    text: str,
    pdf_bytes: bytes | None = None,
    filename: str = "",
) -> tuple[list[ParsedTransaction], list[str]]:
    warnings: list[str] = []
    if bank == Bank.CHASE:
        txns, w = parse_chase(text)
    elif bank == Bank.CHASE_AUTO:
        txns, w = parse_chase_auto(text)
    elif bank == Bank.BOFA:
        txns, w = parse_bofa(text, filename)
    elif bank == Bank.WELLS_FARGO:
        txns, w = parse_wells_fargo(text)
    elif bank == Bank.CAPITAL_ONE:
        if pdf_bytes:
            txns, w = parse_capital_one_from_pdf(pdf_bytes, text, filename)
        else:
            txns, w = parse_capital_one(text, filename)
    else:
        txns, w = parse_generic(text)
        if bank == Bank.UNKNOWN:
            warnings.append("Could not detect bank; used generic PDF parser.")
            if not txns and "CHASE.COM" in text.upper():
                txns, w = parse_chase(text)
                warnings.append("Retried with Chase parser based on chase.com in statement.")
    warnings.extend(w)
    if not txns:
        warnings.append("No transactions parsed; review PDF format or add a bank-specific parser.")
    return txns, warnings
