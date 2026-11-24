from expense_tracker.categorize.locked import is_locked_category_source
from expense_tracker.categorize.reapply import reapply_rules
from expense_tracker.db.store import Store


def test_locked_sources():
    assert is_locked_category_source("override")
    assert is_locked_category_source("llm")
    assert not is_locked_category_source("rule")


def test_reapply_skips_llm_categorized(tmp_path):
    db = tmp_path / "test.db"
    store = Store(str(db))
    store.init_schema()
    upload_id = store.insert_upload(
        filename="t.pdf",
        bank="Test",
        stored_path="/tmp/t.pdf",
        transaction_count=2,
        warnings=[],
    )
    store.insert_transactions(
        upload_id,
        [
            {
                "bank": "Test",
                "account_last4": None,
                "account_kind": None,
                "posted_date": "2026-01-01",
                "description": "RANDOM MERCHANT XYZ",
                "amount": -10.0,
                "category": "Food",
                "category_source": "llm",
                "raw_line": "",
                "dedup_key": "a" * 64,
            },
            {
                "bank": "Test",
                "account_last4": None,
                "account_kind": None,
                "posted_date": "2026-01-02",
                "description": "STARBUCKS",
                "amount": -5.0,
                "category": "Unknown",
                "category_source": "unknown",
                "raw_line": "",
                "dedup_key": "b" * 64,
            },
        ],
    )
    updated = reapply_rules(store)
    txns = {t.description: t for t in store.list_transactions(limit=10)}
    assert txns["RANDOM MERCHANT XYZ"].category == "Food"
    assert txns["RANDOM MERCHANT XYZ"].category_source == "llm"
    assert txns["STARBUCKS"].category == "Food"
    assert updated >= 1
