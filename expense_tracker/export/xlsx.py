from __future__ import annotations

import io
from typing import Sequence

from openpyxl import Workbook

from expense_tracker.db.store import TransactionRow
from expense_tracker.ingest.account import account_label

HEADERS = [
    "Date",
    "Description",
    "Amount",
    "Category",
    "Card",
    "Bank",
    "Last4",
    "Account Type",
    "Source",
]


def _rows_for_export(txns: Sequence[TransactionRow]) -> list[list]:
    out: list[list] = []
    for t in txns:
        out.append(
            [
                t.posted_date,
                t.description,
                t.amount,
                t.category,
                account_label(t.bank, t.account_last4, t.account_kind),
                t.bank,
                t.account_last4 or "",
                t.account_kind or "",
                t.category_source,
            ]
        )
    return out


def transactions_to_xlsx_bytes(txns: Sequence[TransactionRow]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Transactions"
    ws.append(HEADERS)
    for row in _rows_for_export(txns):
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def transactions_to_tsv(txns: Sequence[TransactionRow]) -> str:
    lines = ["\t".join(HEADERS)]
    for row in _rows_for_export(txns):
        escaped = [str(c).replace("\t", " ").replace("\n", " ") for c in row]
        lines.append("\t".join(escaped))
    return "\n".join(lines) + "\n"
