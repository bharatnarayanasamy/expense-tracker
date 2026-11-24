# expense-tracker

## Test data rules (non-negotiable)

Tests and fixtures must **never** contain personal data. No exceptions.

- **No PII:** no real names (yours, friends', merchants' staff), usernames/handles, emails, phone numbers, or addresses.
- **No bank data:** no real card numbers, account or routing numbers, last-4 digits, confirmation codes, transaction IDs, or balances copied from a real statement.
- Never paste text from a real statement, PDF, or CSV export into a test. Write synthetic samples by hand that only mimic the format.
- Use obviously fake values: names like `Jane Example` / `Alex Sample`, card numbers like `4000 1234 5678 9010`, IDs like `1000000000000000001`.
- Real statements belong in `data/` (git-ignored) and must never be committed.
- Before committing, check new or changed test fixtures for anything that looks real.
