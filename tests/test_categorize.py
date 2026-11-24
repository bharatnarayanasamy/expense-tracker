from pathlib import Path

from expense_tracker.categorize.rules import RuleEngine
from expense_tracker.config import PROJECT_ROOT


def test_rule_engine_matches():
    engine = RuleEngine(
        rules_path=PROJECT_ROOT / "config" / "merchant_rules.yaml",
        categories_path=PROJECT_ROOT / "config" / "categories.yaml",
    )
    cat, source = engine.categorize("UBER TRIP 123 SAN FRANCISCO", {})
    assert cat == "Transportation"
    assert source == "rule"


def test_override_wins():
    engine = RuleEngine(
        rules_path=PROJECT_ROOT / "config" / "merchant_rules.yaml",
        categories_path=PROJECT_ROOT / "config" / "categories.yaml",
    )
    cat, source = engine.categorize("UBER TRIP", {"UBER TRIP": "Travel"})
    assert cat == "Travel"
    assert source == "override"
