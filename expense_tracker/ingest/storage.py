from __future__ import annotations

from pathlib import Path

from expense_tracker.config import data_dir


def delete_stored_pdf(stored_path: str) -> bool:
    """Remove an uploaded statement file (PDF/CSV) under the data uploads directory."""
    try:
        path = Path(stored_path).expanduser().resolve(strict=False)
    except OSError:
        return False
    allowed = (data_dir() / "uploads").resolve()
    if path != allowed and allowed not in path.parents:
        return False
    if path.is_file():
        path.unlink()
        return True
    return False
