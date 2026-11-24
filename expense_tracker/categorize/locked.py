from __future__ import annotations

"""Category sources that must not be overwritten by rule reapply or re-import."""

LOCKED_CATEGORY_SOURCES = frozenset({"override", "llm"})


def is_locked_category_source(source: str) -> bool:
    return source in LOCKED_CATEGORY_SOURCES
