from __future__ import annotations

from expense_tracker.categorize.llm_optional import batch_categorize_descriptions, llm_available
from expense_tracker.categorize.rules import RuleEngine
from expense_tracker.db.store import Store


class CategorizationService:
    def __init__(self, store: Store, rules: RuleEngine | None = None) -> None:
        self._store = store
        self._rules = rules or RuleEngine()

    def reload_rules(self) -> None:
        self._rules.reload()

    @property
    def categories(self) -> list[str]:
        return self._rules.categories

    def categorize(self, description: str) -> tuple[str, str]:
        overrides = self._store.list_overrides()
        return self._rules.categorize(description, overrides)

    def apply_override_for_transaction(
        self, txn_id: int, description: str, category: str, save_pattern: bool = True
    ) -> bool:
        ok = self._store.update_transaction_category(txn_id, category, "override")
        if ok and save_pattern:
            pattern = description.upper().strip()[:80]
            self._store.upsert_override(pattern, category)
        return ok

    def maybe_llm_categorize_unknowns(self) -> int:
        if not llm_available():
            return 0
        total = 0
        for _ in range(25):
            unknowns = self._store.transactions_unknown(limit=80)
            if not unknowns:
                break
            items = [(t.id, t.description) for t in unknowns]
            mapping = batch_categorize_descriptions(items, self.categories)
            if not mapping:
                break
            total += self._store.bulk_update_categories(mapping, "llm")
        return total
