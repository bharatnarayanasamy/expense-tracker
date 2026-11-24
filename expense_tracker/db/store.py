from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Iterator

from expense_tracker.config import db_path


@dataclass
class UploadRow:
    id: int
    filename: str
    bank: str
    stored_path: str
    transaction_count: int
    warnings: list[str]
    created_at: str
    account_last4: str | None = None
    account_kind: str | None = None


@dataclass
class TransactionRow:
    id: int
    upload_id: int
    bank: str
    account_last4: str | None
    account_kind: str | None
    posted_date: str
    description: str
    amount: float
    category: str
    category_source: str
    raw_line: str
    dedup_key: str


class Store:
    def __init__(self, path: str | None = None) -> None:
        self._path = path or str(db_path())

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS uploads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    bank TEXT NOT NULL,
                    stored_path TEXT NOT NULL,
                    transaction_count INTEGER NOT NULL DEFAULT 0,
                    warnings_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    upload_id INTEGER NOT NULL,
                    bank TEXT NOT NULL,
                    account_last4 TEXT,
                    posted_date TEXT NOT NULL,
                    description TEXT NOT NULL,
                    amount REAL NOT NULL,
                    category TEXT NOT NULL,
                    category_source TEXT NOT NULL,
                    raw_line TEXT NOT NULL DEFAULT '',
                    dedup_key TEXT NOT NULL UNIQUE,
                    FOREIGN KEY (upload_id) REFERENCES uploads(id)
                );
                CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions(posted_date);
                CREATE INDEX IF NOT EXISTS idx_txn_category ON transactions(category);
                CREATE TABLE IF NOT EXISTS category_overrides (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )
            self._migrate_schema(conn)

    @staticmethod
    def _migrate_schema(conn: sqlite3.Connection) -> None:
        for table, col, decl in (
            ("uploads", "account_last4", "TEXT"),
            ("uploads", "account_kind", "TEXT"),
            ("transactions", "account_kind", "TEXT"),
        ):
            cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
            if col not in cols:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_txn_account ON transactions(account_last4)"
        )
        conn.execute(
            "UPDATE transactions SET category = 'Income' WHERE category = 'Reimbursement'"
        )
        conn.execute(
            "UPDATE category_overrides SET category = 'Income' WHERE category = 'Reimbursement'"
        )

    def insert_upload(
        self,
        filename: str,
        bank: str,
        stored_path: str,
        transaction_count: int,
        warnings: list[str],
        account_last4: str | None = None,
        account_kind: str | None = None,
    ) -> int:
        now = datetime.utcnow().isoformat() + "Z"
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO uploads (
                    filename, bank, stored_path, transaction_count, warnings_json,
                    created_at, account_last4, account_kind
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    filename,
                    bank,
                    stored_path,
                    transaction_count,
                    json.dumps(warnings),
                    now,
                    account_last4,
                    account_kind,
                ),
            )
            return int(cur.lastrowid)

    def insert_transactions(
        self, upload_id: int, rows: list[dict[str, Any]]
    ) -> tuple[int, int]:
        inserted = 0
        skipped = 0
        with self._conn() as conn:
            for row in rows:
                try:
                    conn.execute(
                        """
                        INSERT INTO transactions (
                            upload_id, bank, account_last4, account_kind, posted_date,
                            description, amount, category, category_source, raw_line, dedup_key
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            upload_id,
                            row["bank"],
                            row.get("account_last4"),
                            row.get("account_kind"),
                            row["posted_date"],
                            row["description"],
                            row["amount"],
                            row["category"],
                            row["category_source"],
                            row.get("raw_line", ""),
                            row["dedup_key"],
                        ),
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    skipped += 1
        return inserted, skipped

    def get_upload(self, upload_id: int) -> UploadRow | None:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
        if not r:
            return None
        return self._row_to_upload(r)

    def update_upload_metadata(
        self,
        upload_id: int,
        *,
        bank: str,
        transaction_count: int,
        warnings: list[str],
        account_last4: str | None,
        account_kind: str | None,
    ) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE uploads
                SET bank = ?, transaction_count = ?, warnings_json = ?,
                    account_last4 = ?, account_kind = ?
                WHERE id = ?
                """,
                (
                    bank,
                    transaction_count,
                    json.dumps(warnings),
                    account_last4,
                    account_kind,
                    upload_id,
                ),
            )

    def clear_upload_transactions(self, upload_id: int) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM transactions WHERE upload_id = ?", (upload_id,))

    def delete_upload(self, upload_id: int) -> UploadRow | None:
        upload = self.get_upload(upload_id)
        if not upload:
            return None
        with self._conn() as conn:
            conn.execute("DELETE FROM transactions WHERE upload_id = ?", (upload_id,))
            conn.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
        return upload

    def delete_all_uploads(self) -> list[UploadRow]:
        uploads = self.list_uploads()
        if not uploads:
            return []
        with self._conn() as conn:
            conn.execute("DELETE FROM transactions")
            conn.execute("DELETE FROM uploads")
        return uploads

    def list_uploads(self) -> list[UploadRow]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM uploads ORDER BY id DESC"
            ).fetchall()
        return [self._row_to_upload(r) for r in rows]

    def account_for_upload(self, upload_id: int) -> tuple[str | None, str | None]:
        with self._conn() as conn:
            r = conn.execute(
                """
                SELECT account_last4, account_kind FROM transactions
                WHERE upload_id = ? AND account_last4 IS NOT NULL
                LIMIT 1
                """,
                (upload_id,),
            ).fetchone()
        if not r:
            return None, None
        keys = r.keys()
        kind = r["account_kind"] if "account_kind" in keys else None
        return r["account_last4"], kind

    def list_accounts(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT bank,
                       account_last4,
                       account_kind,
                       COUNT(*) AS txn_count
                FROM transactions
                GROUP BY bank, account_last4, account_kind
                ORDER BY bank, account_last4
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def list_transactions(
        self,
        bank: str | None = None,
        category: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        account_last4: str | None = None,
        limit: int = 5000,
    ) -> list[TransactionRow]:
        clauses: list[str] = []
        params: list[Any] = []
        if bank:
            clauses.append("bank = ?")
            params.append(bank)
        if account_last4:
            clauses.append("account_last4 = ?")
            params.append(account_last4)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if date_from:
            clauses.append("posted_date >= ?")
            params.append(date_from)
        if date_to:
            clauses.append("posted_date <= ?")
            params.append(date_to)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        params.append(limit)
        sql = f"SELECT * FROM transactions{where} ORDER BY posted_date DESC, id DESC LIMIT ?"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self._row_to_txn(r) for r in rows]

    def list_transactions_for_upload(self, upload_id: int) -> list[TransactionRow]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM transactions WHERE upload_id = ? ORDER BY id",
                (upload_id,),
            ).fetchall()
        return [self._row_to_txn(r) for r in rows]

    def get_transaction(self, txn_id: int) -> TransactionRow | None:
        with self._conn() as conn:
            r = conn.execute(
                "SELECT * FROM transactions WHERE id = ?", (txn_id,)
            ).fetchone()
        return self._row_to_txn(r) if r else None

    def update_transaction_category(
        self, txn_id: int, category: str, source: str = "override"
    ) -> bool:
        with self._conn() as conn:
            cur = conn.execute(
                """
                UPDATE transactions SET category = ?, category_source = ?
                WHERE id = ?
                """,
                (category, source, txn_id),
            )
            return cur.rowcount > 0

    def upsert_override(self, pattern: str, category: str) -> None:
        now = datetime.utcnow().isoformat() + "Z"
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO category_overrides (pattern, category, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(pattern) DO UPDATE SET category = excluded.category
                """,
                (pattern.upper(), category, now),
            )

    def list_overrides(self) -> dict[str, str]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT pattern, category FROM category_overrides"
            ).fetchall()
        return {r["pattern"]: r["category"] for r in rows}

    def count_unknown_transactions(self) -> int:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM transactions WHERE category = 'Unknown'"
            ).fetchone()
        return int(row["n"]) if row else 0

    def transactions_unknown(self, limit: int = 200) -> list[TransactionRow]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM transactions
                WHERE category = 'Unknown'
                ORDER BY posted_date DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_txn(r) for r in rows]

    def bulk_update_categories(self, updates: dict[int, str], source: str) -> int:
        count = 0
        with self._conn() as conn:
            for txn_id, category in updates.items():
                cur = conn.execute(
                    """
                    UPDATE transactions SET category = ?, category_source = ?
                    WHERE id = ?
                    """,
                    (category, source, txn_id),
                )
                count += cur.rowcount
        return count

    def aggregate_by_month(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT substr(posted_date, 1, 7) AS month,
                       SUM(CASE WHEN amount < 0 AND category NOT IN ('Transfer', 'Income')
                           THEN -amount ELSE 0 END) AS spend,
                       SUM(CASE WHEN amount > 0 AND category = 'Income'
                           THEN amount ELSE 0 END) AS income
                FROM transactions
                GROUP BY month
                ORDER BY month
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def aggregate_by_month_category(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT substr(posted_date, 1, 7) AS month,
                       category,
                       SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS spend
                FROM transactions
                WHERE amount < 0 AND category NOT IN ('Transfer', 'Income')
                GROUP BY month, category
                ORDER BY month, category
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def aggregate_by_category(self) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT category,
                       SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS spend,
                       COUNT(*) AS count
                FROM transactions
                WHERE amount < 0
                  AND category NOT IN ('Transfer', 'Income')
                GROUP BY category
                ORDER BY spend DESC
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def stats_for_month(self, month: str) -> dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS spend,
                    SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS income,
                    COUNT(*) AS count
                FROM transactions
                WHERE substr(posted_date, 1, 7) = ?
                """,
                (month,),
            ).fetchone()
            top = conn.execute(
                """
                SELECT category, SUM(CASE WHEN amount < 0 THEN -amount ELSE 0 END) AS spend
                FROM transactions
                WHERE substr(posted_date, 1, 7) = ? AND amount < 0
                GROUP BY category
                ORDER BY spend DESC
                LIMIT 1
                """,
                (month,),
            ).fetchone()
        return {
            "month": month,
            "spend": row["spend"] or 0.0,
            "income": row["income"] or 0.0,
            "count": row["count"] or 0,
            "top_category": top["category"] if top else None,
            "top_category_spend": top["spend"] if top else 0.0,
        }

    @staticmethod
    def _row_to_upload(r: sqlite3.Row) -> UploadRow:
        keys = r.keys()
        return UploadRow(
            id=r["id"],
            filename=r["filename"],
            bank=r["bank"],
            stored_path=r["stored_path"],
            transaction_count=r["transaction_count"],
            warnings=json.loads(r["warnings_json"]),
            created_at=r["created_at"],
            account_last4=r["account_last4"] if "account_last4" in keys else None,
            account_kind=r["account_kind"] if "account_kind" in keys else None,
        )

    @staticmethod
    def _row_to_txn(r: sqlite3.Row) -> TransactionRow:
        keys = r.keys()
        return TransactionRow(
            id=r["id"],
            upload_id=r["upload_id"],
            bank=r["bank"],
            account_last4=r["account_last4"],
            account_kind=r["account_kind"] if "account_kind" in keys else None,
            posted_date=r["posted_date"],
            description=r["description"],
            amount=r["amount"],
            category=r["category"],
            category_source=r["category_source"],
            raw_line=r["raw_line"],
            dedup_key=r["dedup_key"],
        )
