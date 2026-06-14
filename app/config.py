"""Load application configuration from config.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"
SOURCE_CONNECTION = "production"


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Missing {CONFIG_PATH.name}. Copy config.example.json to config.json and edit your connection strings."
        )
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def get_connections() -> dict[str, str]:
    return load_config().get("connections", {})


def get_target_connections() -> list[str]:
    return [name for name in get_connections() if name != SOURCE_CONNECTION]


def is_valid_target(env: str) -> bool:
    connections = get_connections()
    return env in connections and env != SOURCE_CONNECTION


def get_connection_string(env: str) -> str:
    try:
        return get_connections()[env]
    except KeyError as exc:
        available = ", ".join(get_connections()) or "(none configured)"
        raise ValueError(f"Unknown connection '{env}'. Available: {available}") from exc


def get_preview_row_limit() -> int:
    config = load_config()
    return int(config.get("preview_row_limit", 500))
