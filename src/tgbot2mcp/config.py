"""Configuration management for tgbot2mcp."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_DIR = Path.home() / ".tgbot2mcp"
DEFAULT_SESSION_DIR = DEFAULT_CONFIG_DIR / "sessions"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


class AppConfig(BaseModel):
    """Application configuration, merged from file + env vars."""

    api_id: int | None = None
    api_hash: str | None = None
    session_dir: Path = Field(default=DEFAULT_SESSION_DIR)
    default_timeout: float = 20.0
    wait_consecutive: float = 2.0
    global_action_delay: float = 0.8
    log_level: str = "INFO"
    discovery_max_depth: int = 5
    discovery_max_repeats: int = 1

    model_config = {"arbitrary_types_allowed": True}


def _load_yaml(path: Path) -> dict[str, Any]:
    if path.exists():
        with open(path, "r") as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    return {}


def load_config(config_path: Path | None = None) -> AppConfig:
    """Load configuration from YAML file, then override with env vars."""
    path = config_path or DEFAULT_CONFIG_FILE
    raw = _load_yaml(path)

    # Environment variable overrides
    env_api_id = os.environ.get("TG_API_ID") or os.environ.get("TELEGRAM_API_ID")
    env_api_hash = os.environ.get("TG_API_HASH") or os.environ.get("TELEGRAM_API_HASH")

    if env_api_id:
        raw["api_id"] = int(env_api_id)
    if env_api_hash:
        raw["api_hash"] = env_api_hash

    # Convert session_dir string to Path if present
    if "session_dir" in raw and isinstance(raw["session_dir"], str):
        raw["session_dir"] = Path(raw["session_dir"])

    return AppConfig(**raw)


def save_config(config: AppConfig, config_path: Path | None = None) -> None:
    """Persist configuration to YAML file."""
    path = config_path or DEFAULT_CONFIG_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    data = config.model_dump()
    # Convert Path to string for YAML serialization
    if isinstance(data.get("session_dir"), Path):
        data["session_dir"] = str(data["session_dir"])

    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def ensure_dirs(config: AppConfig) -> None:
    """Create required directories if they don't exist."""
    config.session_dir.mkdir(parents=True, exist_ok=True)
