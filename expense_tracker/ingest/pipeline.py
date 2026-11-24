from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from expense_tracker.categorize.locked import is_locked_category_source
from expense_tracker.categorize.service import CategorizationService
from expense_tracker.config import data_dir
from expense_tracker.db.store import Store
from expense_tracker.ingest.dedup import make_dedup_key
from expense_tracker.ingest.account import infer_account_kind
from expense_tracker.ingest.detector import detect_bank
from expense_tracker.ingest.models import ParsedTransaction
from expense_tracker.ingest.parsers.base import extract_account_last4
from expense_tracker.ingest.parsers.venmo_csv import parse_venmo_csv
from expense_tracker.ingest.pdf_text import extract_text_from_pdf
from expense_tracker.ingest.parsers import parse_statement

VENMO_BANK = "Venmo"


@dataclass
class ImportResult:
    upload_id: int
    bank: str
    parsed_count: int
    inserted: int
    skipped_duplicates: int
    warnings: list[str]


def _safe_filename(name: str) -> str:
    base = Path(name).name
    base = re.sub(r"[^\w.\- ]", "_", base)
    lower = base.lower()
    if not (lower.endswith(".pdf") or lower.endswith(".csv")):
        base = f"{base}.pdf"
    return base[:200]


def _apply_preserved_categories(
    rows: list[dict], preserved: dict[str, tuple[str, str]]
) -> None:
    for row in rows:
        key = row.get("dedup_key")
        if not key or key not in preserved:
            continue
        category, source = preserved[key]
        if is_locked_category_source(source):
            row["category"] = category
            row["category_source"] = source


def _rows_from_transactions(
    txns: list[ParsedTransaction],
    bank: str,
    account_kind: str,
    categorizer: CategorizationService,
    statement_last4: str | None,
) -> list[dict]:
    rows: list[dict] = []
    for t in txns:
        last4 = t.account_last4 or statement_last4
        t.account_last4 = last4
        cat, source = categorizer.categorize(t.description)
        rows.append(
            {
                "bank": bank,
                "account_last4": last4,
                "account_kind": account_kind,
                "posted_date": t.posted_date,
                "description": t.description,
                "amount": t.amount,
                "category": cat,
                "category_source": source,
                "raw_line": t.raw_line,
                "dedup_key": make_dedup_key(
                    bank,
                    t.posted_date,
                    t.amount,
                    t.description,
                    last4,
                    external_id=t.external_id,
                ),
            }
        )
    return rows


def _persist_import(
    *,
    file_bytes: bytes,
    original_filename: str,
    bank: str,
    account_kind: str,
    statement_last4: str | None,
    txns: list[ParsedTransaction],
    warnings: list[str],
    store: Store,
    categorizer: CategorizationService,
) -> ImportResult:
    safe_name = _safe_filename(original_filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_name}"
    stored_path = data_dir() / "uploads" / stored_name
    stored_path.write_bytes(file_bytes)

    rows = _rows_from_transactions(
        txns, bank, account_kind, categorizer, statement_last4
    )
    upload_last4 = statement_last4
    if not upload_last4 and rows:
        upload_last4 = rows[0].get("account_last4")

    upload_id = store.insert_upload(
        filename=safe_name,
        bank=bank,
        stored_path=str(stored_path),
        transaction_count=len(rows),
        warnings=warnings,
        account_last4=upload_last4,
        account_kind=account_kind,
    )
    inserted, skipped = store.insert_transactions(upload_id, rows)
    categorizer.maybe_llm_categorize_unknowns()

    return ImportResult(
        upload_id=upload_id,
        bank=bank,
        parsed_count=len(rows),
        inserted=inserted,
        skipped_duplicates=skipped,
        warnings=warnings,
    )


def import_csv_bytes(
    csv_bytes: bytes,
    original_filename: str,
    store: Store | None = None,
    categorizer: CategorizationService | None = None,
) -> ImportResult:
    store = store or Store()
    store.init_schema()
    categorizer = categorizer or CategorizationService(store)

    try:
        text = csv_bytes.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("CSV must be UTF-8 (Venmo export).") from exc

    header_hint = text[:800].lower()
    if "venmo" not in original_filename.lower() and "account statement - (@" not in header_hint:
        raise ValueError("Unsupported CSV; only Venmo account statements are supported.")

    txns, warnings = parse_venmo_csv(text)
    statement_last4 = txns[0].account_last4 if txns else None

    return _persist_import(
        file_bytes=csv_bytes,
        original_filename=original_filename,
        bank=VENMO_BANK,
        account_kind="wallet",
        statement_last4=statement_last4,
        txns=txns,
        warnings=warnings,
        store=store,
        categorizer=categorizer,
    )


def import_pdf_bytes(
    pdf_bytes: bytes,
    original_filename: str,
    store: Store | None = None,
    categorizer: CategorizationService | None = None,
) -> ImportResult:
    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("File is not a valid PDF.")

    store = store or Store()
    store.init_schema()
    categorizer = categorizer or CategorizationService(store)

    extract = extract_text_from_pdf(pdf_bytes)
    bank_enum = detect_bank(extract.text)
    txns, parse_warnings = parse_statement(
        bank_enum, extract.text, pdf_bytes=pdf_bytes, filename=original_filename
    )
    warnings = list(parse_warnings)
    if extract.low_confidence:
        warnings.append(
            "Low text extraction from PDF; if this is a scanned statement, OCR is not supported in v1."
        )

    bank = bank_enum.value
    account_kind = infer_account_kind(extract.text, bank_enum)
    statement_last4 = extract_account_last4(extract.text)

    return _persist_import(
        file_bytes=pdf_bytes,
        original_filename=original_filename,
        bank=bank,
        account_kind=account_kind,
        statement_last4=statement_last4,
        txns=txns,
        warnings=warnings,
        store=store,
        categorizer=categorizer,
    )


def import_statement_bytes(
    data: bytes,
    original_filename: str,
    store: Store | None = None,
    categorizer: CategorizationService | None = None,
) -> ImportResult:
    if original_filename.lower().endswith(".csv"):
        return import_csv_bytes(data, original_filename, store=store, categorizer=categorizer)
    return import_pdf_bytes(data, original_filename, store=store, categorizer=categorizer)


def import_statement_path(path: Path, store: Store | None = None) -> ImportResult:
    return import_statement_bytes(path.read_bytes(), path.name, store=store)


def import_pdf_path(path: Path, store: Store | None = None) -> ImportResult:
    return import_statement_bytes(path.read_bytes(), path.name, store=store)


def reprocess_upload(upload_id: int, store: Store | None = None) -> ImportResult:
    """Re-parse a stored upload and replace its transactions (same upload id)."""
    store = store or Store()
    store.init_schema()
    upload = store.get_upload(upload_id)
    if not upload:
        raise ValueError(f"Upload {upload_id} not found.")

    path = Path(upload.stored_path)
    if not path.is_file():
        raise ValueError(f"Stored file missing: {path}")

    file_bytes = path.read_bytes()
    categorizer = CategorizationService(store)

    if upload.filename.lower().endswith(".csv") or path.suffix.lower() == ".csv":
        text = file_bytes.decode("utf-8-sig")
        txns, warnings = parse_venmo_csv(text)
        bank = VENMO_BANK
        account_kind = "wallet"
        statement_last4 = txns[0].account_last4 if txns else upload.account_last4
    else:
        extract = extract_text_from_pdf(file_bytes)
        bank_enum = detect_bank(extract.text)
        txns, parse_warnings = parse_statement(
            bank_enum,
            extract.text,
            pdf_bytes=file_bytes,
            filename=upload.filename,
        )
        warnings = list(parse_warnings)
        if extract.low_confidence:
            warnings.append(
                "Low text extraction from PDF; if this is a scanned statement, OCR is not supported in v1."
            )
        bank = bank_enum.value
        account_kind = infer_account_kind(extract.text, bank_enum)
        statement_last4 = extract_account_last4(extract.text)

    preserved: dict[str, tuple[str, str]] = {}
    for txn in store.list_transactions_for_upload(upload_id):
        if is_locked_category_source(txn.category_source):
            preserved[txn.dedup_key] = (txn.category, txn.category_source)

    rows = _rows_from_transactions(
        txns, bank, account_kind, categorizer, statement_last4
    )
    _apply_preserved_categories(rows, preserved)
    upload_last4 = statement_last4
    if not upload_last4 and rows:
        upload_last4 = rows[0].get("account_last4")

    store.clear_upload_transactions(upload_id)
    store.update_upload_metadata(
        upload_id,
        bank=bank,
        transaction_count=len(rows),
        warnings=warnings,
        account_last4=upload_last4,
        account_kind=account_kind,
    )
    inserted, skipped = store.insert_transactions(upload_id, rows)
    categorizer.maybe_llm_categorize_unknowns()

    return ImportResult(
        upload_id=upload_id,
        bank=bank,
        parsed_count=len(rows),
        inserted=inserted,
        skipped_duplicates=skipped,
        warnings=warnings,
    )
