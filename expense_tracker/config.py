from __future__ import annotations

import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"


def data_dir() -> Path:
    raw = os.environ.get("EXPENSE_TRACKER_DATA")
    if raw:
        path = Path(raw).expanduser()
    else:
        path = Path.home() / ".expense-tracker"
    path.mkdir(parents=True, exist_ok=True)
    (path / "uploads").mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "data.db"


def config_dir() -> Path:
    override = os.environ.get("EXPENSE_TRACKER_CONFIG")
    if override:
        return Path(override).expanduser()
    return DEFAULT_CONFIG_DIR


def categories_yaml() -> Path:
    return config_dir() / "categories.yaml"


def merchant_rules_yaml() -> Path:
    return config_dir() / "merchant_rules.yaml"


def static_dir() -> Path:
    built = PACKAGE_ROOT / "static"
    if built.is_dir() and any(built.iterdir()):
        return built
    dev = PROJECT_ROOT / "frontend" / "dist"
    if dev.is_dir():
        return dev
    return built
