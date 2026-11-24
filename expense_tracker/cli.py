from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
import uvicorn

from expense_tracker.config import PROJECT_ROOT, data_dir, db_path


def _load_dotenv() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

from expense_tracker.db.store import Store
from expense_tracker.ingest.pipeline import import_statement_path, reprocess_upload
from expense_tracker.insights.aggregates import build_insights

app = typer.Typer(
    name="expense-tracker",
    help="Local PDF expense tracker with categorization and dashboard.",
)


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address (local only recommended)."),
    port: int = typer.Option(8765, help="HTTP port."),
    reload: bool = typer.Option(False, help="Auto-reload API (dev)."),
) -> None:
    """Start the web UI and API."""
    store = Store()
    store.init_schema()
    typer.echo(f"Data directory: {data_dir()}")
    typer.echo(f"Database: {db_path()}")
    typer.echo(f"Open http://{host}:{port}")
    uvicorn.run(
        "expense_tracker.app.main:app",
        host=host,
        port=port,
        reload=reload,
    )


@app.command("import")
def import_cmd(
    pdf_path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
) -> None:
    """Import a PDF statement from the command line."""
    store = Store()
    store.init_schema()
    result = import_statement_path(pdf_path, store=store)
    typer.echo(json.dumps(result.__dict__, indent=2))


@app.command("import-dir")
def import_dir_cmd(
    directory: Path = typer.Argument(..., exists=True, file_okay=False, readable=True),
) -> None:
    """Import every PDF in a folder (non-recursive)."""
    store = Store()
    store.init_schema()
    files = sorted(directory.glob("*.pdf")) + sorted(directory.glob("*.csv"))
    if not files:
        typer.echo(f"No PDF or CSV files in {directory}", err=True)
        raise typer.Exit(code=1)
    for file_path in files:
        result = import_statement_path(file_path, store=store)
        typer.echo(
            f"{file_path.name}: {result.parsed_count} parsed, "
            f"{result.inserted} inserted ({result.bank})"
        )


@app.command()
def stats(
    month: Optional[str] = typer.Option(None, help="YYYY-MM month filter."),
) -> None:
    """Print spend insights as JSON."""
    store = Store()
    store.init_schema()
    if month:
        typer.echo(json.dumps(store.stats_for_month(month), indent=2))
    else:
        typer.echo(json.dumps(build_insights(store), indent=2))


@app.command("delete-upload")
def delete_upload_cmd(
    upload_id: int = typer.Argument(..., help="Upload id from list or UI."),
) -> None:
    """Delete an imported PDF, its file, and all linked transactions."""
    from expense_tracker.ingest.storage import delete_stored_pdf

    store = Store()
    store.init_schema()
    removed = store.delete_upload(upload_id)
    if not removed:
        typer.echo(f"Upload {upload_id} not found.", err=True)
        raise typer.Exit(code=1)
    delete_stored_pdf(removed.stored_path)
    typer.echo(json.dumps({"deleted": upload_id, "filename": removed.filename}, indent=2))


@app.command("reprocess-uploads")
def reprocess_uploads_cmd(
    zero_only: bool = typer.Option(
        True,
        "--zero-only/--all",
        help="Only re-parse uploads that currently have 0 transactions.",
    ),
) -> None:
    """Re-run PDF parsers on stored uploads (after parser fixes)."""
    store = Store()
    store.init_schema()
    uploads = store.list_uploads()
    if zero_only:
        uploads = [u for u in uploads if u.transaction_count == 0]
    if not uploads:
        typer.echo("No uploads to reprocess.")
        raise typer.Exit(code=0)
    for u in uploads:
        try:
            result = reprocess_upload(u.id, store=store)
            typer.echo(
                f"#{u.id} {u.filename}: parsed {result.parsed_count}, "
                f"inserted {result.inserted}, skipped dupes {result.skipped_duplicates}"
            )
        except ValueError as exc:
            typer.echo(f"#{u.id} {u.filename}: skipped — {exc}", err=True)


@app.command("recategorize")
def recategorize_cmd() -> None:
    """Re-apply merchant_rules.yaml to existing transactions (keeps manual overrides)."""
    from expense_tracker.categorize.reapply import reapply_rules

    store = Store()
    store.init_schema()
    count = reapply_rules(store)
    typer.echo(f"Updated {count} transactions.")


@app.command()
def init_db() -> None:
    """Create or migrate the local SQLite database."""
    store = Store()
    store.init_schema()
    typer.echo(f"Initialized {db_path()}")


if __name__ == "__main__":
    app()
