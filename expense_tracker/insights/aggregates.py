from __future__ import annotations

from typing import Any

from expense_tracker.db.store import Store


def build_insights(store: Store) -> dict[str, Any]:
    by_month = store.aggregate_by_month()
    by_month_category = store.aggregate_by_month_category()
    by_category = store.aggregate_by_category()

    total_spend = sum(r["spend"] or 0 for r in by_category)
    top_cat = by_category[0]["category"] if by_category else None
    top_cat_spend = by_category[0]["spend"] if by_category else 0.0

    mom_delta_pct: float | None = None
    if len(by_month) >= 2:
        prev = by_month[-2]["spend"] or 0
        curr = by_month[-1]["spend"] or 0
        if prev > 0:
            mom_delta_pct = round((curr - prev) / prev * 100, 1)

    latest_month = by_month[-1]["month"] if by_month else None
    latest_spend = by_month[-1]["spend"] if by_month else 0.0

    return {
        "total_spend": round(total_spend, 2),
        "top_category": top_cat,
        "top_category_spend": round(top_cat_spend or 0, 2),
        "latest_month": latest_month,
        "latest_month_spend": round(latest_spend or 0, 2),
        "month_over_month_delta_pct": mom_delta_pct,
        "by_month": by_month,
        "by_month_category": by_month_category,
        "by_category": by_category,
    }
