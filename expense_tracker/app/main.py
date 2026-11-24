from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from expense_tracker.categorize.llm_optional import llm_available
from expense_tracker.categorize.service import CategorizationService
from expense_tracker.config import static_dir
from expense_tracker.db.store import Store, TransactionRow
from expense_tracker.export.xlsx import transactions_to_tsv, transactions_to_xlsx_bytes
from expense_tracker.ingest.account import account_label
from expense_tracker.ingest.pipeline import import_statement_bytes
from expense_tracker.ingest.storage import delete_stored_pdf
from expense_tracker.insights.aggregates import build_insights

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Expense Tracker", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_store: Store | None = None
_categorizer: CategorizationService | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
        _store.init_schema()
    return _store


def get_categorizer() -> CategorizationService:
    global _categorizer
    if _categorizer is None:
        _categorizer = CategorizationService(get_store())
    return _categorizer


def txn_to_dict(t: TransactionRow) -> dict[str, Any]:
    return {
        "id": t.id,
        "upload_id": t.upload_id,
        "bank": t.bank,
        "account_last4": t.account_last4,
        "account_kind": t.account_kind,
        "account_label": account_label(t.bank, t.account_last4, t.account_kind),
        "posted_date": t.posted_date,
        "description": t.description,
        "amount": t.amount,
        "category": t.category,
        "category_source": t.category_source,
    }


class CategoryUpdate(BaseModel):
    category: str = Field(min_length=1, max_length=64)
    save_pattern: bool = True


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/categories")
def list_categories() -> dict[str, list[str]]:
    return {"categories": get_categorizer().categories}


@app.get("/api/accounts")
def list_accounts() -> dict[str, Any]:
    store = get_store()
    rows = store.list_accounts()
    return {
        "accounts": [
            {
                **dict(row),
                "label": account_label(
                    row["bank"],
                    row["account_last4"],
                    row["account_kind"] if row["account_kind"] else None,
                ),
            }
            for row in rows
        ]
    }


@app.get("/api/uploads")
def list_uploads() -> dict[str, Any]:
    store = get_store()
    uploads = store.list_uploads()
    payload = []
    for u in uploads:
        last4 = u.account_last4
        kind = u.account_kind
        if not last4:
            last4, kind_from_txn = store.account_for_upload(u.id)
            kind = kind or kind_from_txn
        payload.append(
            {
                "id": u.id,
                "filename": u.filename,
                "bank": u.bank,
                "account_last4": last4,
                "account_kind": kind,
                "account_label": account_label(u.bank, last4, kind),
                "transaction_count": u.transaction_count,
                "warnings": u.warnings,
                "created_at": u.created_at,
            }
        )
    return {"uploads": payload}


@app.delete("/api/uploads")
def delete_all_uploads() -> dict[str, Any]:
    store = get_store()
    removed = store.delete_all_uploads()
    files_deleted = 0
    for row in removed:
        if delete_stored_pdf(row.stored_path):
            files_deleted += 1
    return {
        "removed_count": len(removed),
        "files_deleted": files_deleted,
    }


@app.delete("/api/uploads/{upload_id}")
def delete_upload(upload_id: int) -> dict[str, Any]:
    store = get_store()
    removed = store.delete_upload(upload_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Upload not found.")
    file_deleted = delete_stored_pdf(removed.stored_path)
    remaining_same_name = sum(
        1 for u in store.list_uploads() if u.filename == removed.filename
    )
    return {
        "id": removed.id,
        "filename": removed.filename,
        "transactions_removed": removed.transaction_count,
        "file_deleted": file_deleted,
        "remaining_same_filename": remaining_same_name,
    }


@app.post("/api/uploads/{upload_id}/delete")
def delete_upload_post(upload_id: int) -> dict[str, Any]:
    """Fallback for clients/environments that block HTTP DELETE."""
    return delete_upload(upload_id)


@app.post("/api/uploads")
async def upload_statement(file: UploadFile = File(...)) -> dict[str, Any]:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename.")
    lower = file.filename.lower()
    if not (lower.endswith(".pdf") or lower.endswith(".csv")):
        raise HTTPException(
            status_code=400,
            detail="Supported uploads: PDF bank statements and Venmo CSV exports.",
        )
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File exceeds 25MB limit.")
    try:
        result = import_statement_bytes(
            data,
            file.filename,
            store=get_store(),
            categorizer=get_categorizer(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read statement: {exc}. Use a text PDF or Venmo CSV export.",
        ) from exc
    return {
        "upload_id": result.upload_id,
        "bank": result.bank,
        "parsed_count": result.parsed_count,
        "inserted": result.inserted,
        "skipped_duplicates": result.skipped_duplicates,
        "warnings": result.warnings,
    }


@app.get("/api/transactions")
def list_transactions(
    bank: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    account_last4: str | None = None,
) -> dict[str, Any]:
    txns = get_store().list_transactions(
        bank=bank,
        category=category,
        date_from=date_from,
        date_to=date_to,
        account_last4=account_last4,
    )
    return {"transactions": [txn_to_dict(t) for t in txns]}


@app.patch("/api/transactions/{txn_id}")
def update_category(txn_id: int, body: CategoryUpdate) -> dict[str, Any]:
    cats = get_categorizer().categories
    if body.category not in cats:
        raise HTTPException(status_code=400, detail="Invalid category.")
    txn = get_store().get_transaction(txn_id)
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found.")
    ok = get_categorizer().apply_override_for_transaction(
        txn_id, txn.description, body.category, save_pattern=body.save_pattern
    )
    if not ok:
        raise HTTPException(status_code=500, detail="Update failed.")
    updated = get_store().get_transaction(txn_id)
    assert updated
    return {"transaction": txn_to_dict(updated)}


@app.get("/api/insights")
def insights() -> dict[str, Any]:
    return build_insights(get_store())


@app.get("/api/export.xlsx")
def export_xlsx(
    bank: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    account_last4: str | None = None,
) -> Response:
    txns = get_store().list_transactions(
        bank=bank,
        category=category,
        date_from=date_from,
        date_to=date_to,
        account_last4=account_last4,
    )
    content = transactions_to_xlsx_bytes(txns)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="transactions.xlsx"'},
    )


@app.get("/api/export.tsv")
def export_tsv(
    bank: str | None = None,
    category: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    account_last4: str | None = None,
) -> Response:
    txns = get_store().list_transactions(
        bank=bank,
        category=category,
        date_from=date_from,
        date_to=date_to,
        account_last4=account_last4,
    )
    return Response(content=transactions_to_tsv(txns), media_type="text/tab-separated-values")


@app.get("/api/categorize/status")
def categorize_status() -> dict[str, Any]:
    store = get_store()
    return {
        "llm_available": llm_available(),
        "unknown_count": store.count_unknown_transactions(),
    }


@app.post("/api/categorize/unknowns")
def categorize_unknowns() -> dict[str, Any]:
    if not llm_available():
        raise HTTPException(
            status_code=400,
            detail=(
                "ANTHROPIC_API_KEY is not set. Add it to expense-tracker/.env "
                "and restart ./run.sh serve."
            ),
        )
    store = get_store()
    updated = get_categorizer().maybe_llm_categorize_unknowns()
    return {
        "updated": updated,
        "remaining_unknowns": store.count_unknown_transactions(),
        "llm_available": True,
    }


def mount_static() -> None:
    root = static_dir()
    index = root / "index.html"
    if not index.is_file():
        return

    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

    @app.get("/")
    def spa_index() -> FileResponse:
        return FileResponse(index)

    @app.get("/app.js")
    def static_app_js() -> FileResponse:
        return FileResponse(root / "app.js")

    @app.get("/styles.css")
    def static_styles() -> FileResponse:
        return FileResponse(root / "styles.css")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = root / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index)


mount_static()
