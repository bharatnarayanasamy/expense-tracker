from expense_tracker.ingest.detector import Bank, detect_bank


def test_detect_chase():
    assert detect_bank("JPMorgan Chase Bank statement") == Bank.CHASE
    assert detect_bank("www.chase.com/amazon Prime Visa") == Bank.CHASE


def test_detect_bofa():
    assert detect_bank("Bank of America account summary") == Bank.BOFA


def test_detect_wells():
    assert detect_bank("Wells Fargo checking") == Bank.WELLS_FARGO


def test_detect_capital_one():
    assert detect_bank("Capital One credit card") == Bank.CAPITAL_ONE


def test_detect_unknown():
    assert detect_bank("Random credit union") == Bank.UNKNOWN
