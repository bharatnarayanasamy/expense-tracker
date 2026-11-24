# Expense Tracker

Local-first app to upload **PDF bank statements**, parse transactions, categorize spending, and view insights in a web dashboard.

## Quick start

You do **not** need `pip install -e .` or the `expense-tracker` command. Use `./run.sh` instead.

```bash
cd expense-tracker
python3 -m venv .venv
source .venv/bin/activate

chmod +x scripts/*.sh run.sh
./scripts/bootstrap.sh          # exports Keychain CAs + pip install -r requirements.txt

./run.sh serve
# Open http://127.0.0.1:8765
```

**Do not run** `pip install -e .` on corporate networks — use bootstrap + `./run.sh` instead. More help: [scripts/INSTALL-CORP-NETWORK.md](scripts/INSTALL-CORP-NETWORK.md).

Bundled static UI works without an npm build. Optional React build: `cd frontend && npm install && npm run build`.

## Troubleshooting pip install

| Symptom | What to do |
|--------|------------|
| **`expense-tracker: command not found`** | Normal if you skipped editable install. Use **`./run.sh serve`**. |
| **`AutoDesk WW HQ Root CA` / SSL** | Run `./scripts/export-macos-certs.sh`, then `./scripts/bootstrap.sh`. Or install your company root CA in Keychain (System). |
| **`503` from files.pythonhosted.org** | Retry in a few minutes, try off VPN, or use company `PIP_INDEX_URL` if you have one. |
| **`Cannot import setuptools.build_meta`** | Do **not** use `pip install -e .`. Run `./scripts/bootstrap.sh` (uses `ensurepip` first). |
| **Python 3.14** | Supported; if wheels are missing, try **`python3.12 -m venv .venv`** and bootstrap again. |

## CLI

```bash
./run.sh import ~/Downloads/chase-statement.pdf
./run.sh import-dir ~/path/to/statement-folder
./run.sh stats
./run.sh stats --month 2026-01
./run.sh reprocess-uploads    # re-parse stored PDFs after parser updates
```

### Supported statement shapes (PDF)

| Account | Typical filename | Parser notes |
|--------|-------------------|--------------|
| BoFA **credit card** (Visa Signature) | `eStmt_YYYY-MM-DD.pdf` | Dual-date lines `MM/DD MM/DD … amount`; year from statement closing date |
| BoFA **checking** (Adv Plus Banking) | `eStmt_YYYY-MM-DD.pdf` | Single line `MM/DD/YY description amount` |
| Capital One credit | `Statement_MMYYYY_XXXX.pdf` | Transaction table inside PDF |
| Chase **Prime Visa** | `*statements-XXXX*.pdf` | Chase card layout |
| Chase **Auto loan** | `*statements-XXXX*.pdf` | One payment per statement (not a credit card) |
| **Venmo** | `VenmoStatement_*.csv` | From Venmo → Settings → Statements; uses Venmo transaction IDs for dedup |

BoFA credit and checking both use `eStmt_…` names — detection is by statement content (Visa Signature vs Adv Plus Banking), not the folder name.

Venmo CSV amounts follow Venmo’s sign convention (+ in, − out). They may overlap bank lines (e.g. Venmo cashout on checking); use Venmo for split-bill detail and bank for cash flow, or filter by account in the UI.

## Data location

- Default data dir: `~/.expense-tracker/` (SQLite + uploaded PDFs)
- Override: `EXPENSE_TRACKER_DATA=/path/to/data`

## Configuration

- Categories: `config/categories.yaml`
- Merchant rules: `config/merchant_rules.yaml`
- Optional LLM for `Unknown` rows: copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY` (descriptions only; PDFs are never sent).

## Supported banks (PDF)

Heuristic detection plus dedicated parsers for **Chase**, **Bank of America**, **Wells Fargo**, and **Capital One**, with a **generic** fallback for other layouts.

Scanned/image-only PDFs without extractable text are not supported in v1.

## Manual test checklist

1. `./run.sh serve` binds to `127.0.0.1:8765` only.
2. Upload a PDF → see bank name, transaction count, and any parse warnings.
3. Transactions tab → filter, change category, **Copy for Excel**, download `.xlsx`.
4. Insights tab → monthly bars and KPI cards update after import.
5. Re-upload same statement → duplicates skipped (`skipped_duplicates` in upload response).
6. (Optional) Set `ANTHROPIC_API_KEY` → **Categorize unknowns (LLM)** on Upload tab.

## Development

```bash
pytest
cd frontend && npm run dev   # proxies API to :8765 when serve is running
```
