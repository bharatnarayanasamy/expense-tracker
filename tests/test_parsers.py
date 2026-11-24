from expense_tracker.ingest.parsers.bofa import parse_bofa
from expense_tracker.ingest.parsers.capital_one import parse_capital_one
from expense_tracker.ingest.parsers.chase import parse_chase
from expense_tracker.ingest.parsers.generic import parse_generic
from expense_tracker.ingest.parsers.wells_fargo import parse_wells_fargo


CHASE_SAMPLE = """
JPMorgan Chase
Statement Period: 01/01/2026 to 01/31/2026
Account Number: XXXX XXXX XXXX 1234

01/05 STARBUCKS STORE 12345 SEATTLE WA 5.67
01/12 AMAZON MARKETPLACE 42.19
01/20 PAYMENT THANK YOU -500.00
"""

BOFA_SAMPLE = """
Bank of America
Account # ****5678

01/03/2026 CHECKCARD 0102 WHOLE FOODS MARKET 86.44
01/15/2026 DIRECT DEP PAYROLL 2500.00
"""

BOFA_CHECKING_SAMPLE = """
Bank of America
Adv Plus Banking
06/18/2026 STATE TAX REFUND DES:TAXRFD ID:987 INDN:EXAMPLE, JANE CO 864.21
06/11/2026 CHECKCARD 0610 CORNER MARKET ANYTOWN ZZ -23.58
06/04/2026 VENMO DES:CASHOUT ID:456 INDN:JANE 137.50
"""

BOFA_CC_SAMPLE = """
Bank of America
Visa Signature
Account# 4000 3381 6620 3927
June 10 - July 9, 2026
Statement Closing Date 07/09/2026
06/14 06/15 PARKWAY - 42 ELM ST. SPRINGFIELDZZ 3829 3927 18.75
07/01 07/02 ONLINE/MOBILE RECURRING FROM CHK 3141 5926 3927 -742.18
07/09 07/09 REWARDS CASHBACK 7711 3927 -3.40
"""

BOFA_CC_DEC_JAN_SAMPLE = """
Bank of America
Visa Signature
Account# 4000 3381 6620 3927
December 3 - January 2, 2027
Statement Closing Date 01/02/2027
12/18 12/19 PAYMENT FROM CHK 3141 CONF#zq7r2m4k 5512 3927 -250.00
01/01 01/02 WHOLE FOODS MARKET 8890 3927 61.37
"""


def test_generic_parser_finds_lines():
    txns, _ = parse_generic("01/10/2026 UBER TRIP 12.34\n01/11/2026 NETFLIX.COM 15.99")
    assert len(txns) >= 2
    assert txns[0].posted_date == "2026-01-10"


def test_chase_parser():
    txns, _ = parse_chase(CHASE_SAMPLE)
    assert len(txns) >= 2
    descriptions = " ".join(t.description for t in txns).upper()
    assert "STARBUCKS" in descriptions


def test_bofa_parser():
    txns, _ = parse_bofa(BOFA_SAMPLE)
    assert len(txns) >= 2
    whole = next(t for t in txns if "WHOLE FOODS" in t.description)
    assert whole.amount == -86.44
    payroll = next(t for t in txns if "PAYROLL" in t.description)
    assert payroll.amount == 2500.0


def test_bofa_checking_deposit_signs():
    txns, _ = parse_bofa(BOFA_CHECKING_SAMPLE)
    tax = next(t for t in txns if "STATE TAX" in t.description)
    assert tax.amount == 864.21
    assert next(t for t in txns if "CORNER MARKET" in t.description).amount == -23.58
    assert next(t for t in txns if "VENMO" in t.description).amount == 137.5


def test_bofa_credit_card_estmt():
    txns, _ = parse_bofa(BOFA_CC_SAMPLE, filename="eStmt_2026-07-09.pdf")
    assert len(txns) == 3
    by_desc = {t.description.split()[0]: t for t in txns}
    assert by_desc["PARKWAY"].amount == -18.75
    assert by_desc["ONLINE/MOBILE"].amount == -742.18
    assert by_desc["REWARDS"].amount == -3.4
    assert txns[0].account_last4 == "3927"


def test_bofa_credit_card_dec_jan_year():
    txns, _ = parse_bofa(BOFA_CC_DEC_JAN_SAMPLE, filename="eStmt_2027-01-02.pdf")
    dates = {t.description.split()[0]: t.posted_date for t in txns}
    assert dates["PAYMENT"] == "2026-12-19"
    assert dates["WHOLE"] == "2027-01-02"


def test_wells_parser():
    text = "Wells Fargo\n01/05 GROCERY OUTLET 44.10\n01/12 PAYROLL DEPOSIT 1200.00\n2026"
    txns, _ = parse_wells_fargo(text)
    assert len(txns) >= 1


def test_capital_one_parser():
    text = "Capital One\n01/08 NETFLIX.COM 15.99\n2026"
    txns, _ = parse_capital_one(text)
    assert len(txns) >= 1
