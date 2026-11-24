from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from expense_tracker.config import categories_yaml, merchant_rules_yaml


@dataclass
class MerchantRule:
    match: str
    category: str
    is_regex: bool


class RuleEngine:
    def __init__(
        self,
        rules_path: Path | None = None,
        categories_path: Path | None = None,
    ) -> None:
        self._rules_path = rules_path or merchant_rules_yaml()
        self._categories_path = categories_path or categories_yaml()
        self._rules: list[MerchantRule] = []
        self._categories: list[str] = []
        self.reload()

    def reload(self) -> None:
        with open(self._categories_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        self._categories = list(data.get("categories") or [])

        with open(self._rules_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        self._rules = []
        for item in raw.get("rules") or []:
            match = str(item.get("match", "")).strip()
            category = str(item.get("category", "")).strip()
            if not match or not category:
                continue
            is_regex = match.lower().startswith("regex:")
            if is_regex:
                match = match[6:].strip()
            self._rules.append(MerchantRule(match=match, category=category, is_regex=is_regex))

    @property
    def categories(self) -> list[str]:
        return list(self._categories)

    def categorize(self, description: str, overrides: dict[str, str]) -> tuple[str, str]:
        upper = description.upper()
        for pattern, category in overrides.items():
            if pattern in upper:
                return category, "override"

        for rule in self._rules:
            if rule.is_regex:
                if re.search(rule.match, description, re.IGNORECASE):
                    return rule.category, "rule"
            elif rule.match.upper() in upper:
                return rule.category, "rule"

        return "Unknown", "unknown"
