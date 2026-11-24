from __future__ import annotations

from expense_tracker.categorize.locked import is_locked_category_source
from expense_tracker.categorize.service import CategorizationService
from expense_tracker.db.store import Store


def reapply_rules(store: Store | None = None) -> int:
    """Re-run merchant rules on transactions not locked by user or AI categorization."""
    store = store or Store()
    store.init_schema()
    cat = CategorizationService(store)
    cat.reload_rules()
    updated = 0
    for txn in store.list_transactions(limit=100_000):
        if is_locked_category_source(txn.category_source):
            continue
        new_cat, source = cat.categorize(txn.description)
        if new_cat != txn.category or source != txn.category_source:
            store.update_transaction_category(txn.id, new_cat, source)
            updated += 1
    return updated
