from expense_tracker.ingest.parsers.venmo_csv import parse_venmo_csv

SAMPLE = """Account Statement - (@Jane-Example) ,,,,
Account Activity,,,,,
,ID,Datetime,Type,Status,Note,From,To,Amount (total),Amount (tip),Amount (tax),Amount (fee),Tax Rate,Tax Exempt,Funding Source,Destination,Beginning Balance,Ending Balance,Statement Period Venmo Fees,Terminal Location,Year to Date Venmo Fees,Disclaimer
,,,,,,,,,,,,,,,,$83.40,,,,,
,52038817KQ9917263,2026-08-11T19:22:07,Payment,Complete,Tacos,Alex Sample,Jane Example,+ $14.25,,0,,0,,,Venmo balance,,,,Venmo,,
,7316024859173306482,2026-08-17T12:05:44,Payment,Complete,Concert tickets,Jane Example,Sam Placeholder,- $62.00,,0,,0,,Venmo balance,,,,,Venmo,,
,2948715063398201157,2026-08-29T21:48:10,Payment,Complete,Groceries,Jane Example,Pat Testuser,- $19.90,,0,,0,,Venmo balance,,,,,Venmo,,
"""


def test_venmo_csv_parses_rows_and_amount_signs():
    txns, warnings = parse_venmo_csv(SAMPLE)
    assert not warnings or "no transactions" not in warnings[0].lower()
    assert len(txns) == 3
    assert txns[0].amount == 14.25
    assert txns[0].description == "Venmo: Tacos"
    assert txns[1].amount == -62.0
    assert txns[2].external_id == "2948715063398201157"
    assert txns[0].account_last4 == "mple"
