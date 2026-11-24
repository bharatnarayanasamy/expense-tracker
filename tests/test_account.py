from expense_tracker.ingest.account import account_label, infer_account_kind
from expense_tracker.ingest.detector import Bank


def test_infer_credit_from_prime_visa():
    assert infer_account_kind("YOUR PRIME VISA POINTS chase.com", Bank.CHASE) == "credit"


def test_infer_debit():
    assert infer_account_kind("DEBIT CARD PURCHASE CHECKING", Bank.BOFA) == "debit"


def test_account_label():
    assert account_label("Chase", "4719", "credit") == "Chase Credit ••4719"
    assert account_label("Bank of America", "1234", "debit") == "Bank of America Debit ••1234"
