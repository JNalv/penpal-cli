"""XDG paths, defaults, config loading, and environment variable overrides."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def config_dir() -> Path:
    return _xdg_config_home() / "penpal"


def data_dir() -> Path:
    return _xdg_data_home() / "penpal"


def db_path() -> Path:
    return data_dir() / "penpal.db"


def skills_dir() -> Path:
    return config_dir() / "skills"


def config_file() -> Path:
    return config_dir() / "config.toml"


def credentials_file() -> Path:
    return config_dir() / "credentials"


MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-20250514",
    "opus": "claude-opus-4-20250514",
}

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MAX_TOKENS = 4096
DEFAULT_POLL_INTERVAL = 180


@dataclass(frozen=True)
class PenpalConfig:
    model: str
    max_tokens: int
    poll_interval: int
    preview_lines: int
    extraction_enabled: bool
    extraction_min_lines: int
    extraction_output_dir: Path
    skills_dir: Path
    db_path: Path
    config_file: Path


def load_config() -> PenpalConfig:
    """Load config from toml file and apply environment overrides."""
    # Ensure directories exist
    config_dir().mkdir(parents=True, exist_ok=True)
    data_dir().mkdir(parents=True, exist_ok=True)
    skills_dir().mkdir(parents=True, exist_ok=True)

    raw: dict = {}
    cf = config_file()
    if cf.exists():
        try:
            with open(cf, "rb") as f:
                raw = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            import sys
            print(f"Error: config.toml is invalid: {e}", file=sys.stderr)
            print(f"  Fix or delete: {cf}", file=sys.stderr)
            sys.exit(1)

    defaults = raw.get("defaults", {})
    display = raw.get("display", {})
    extraction = raw.get("extraction", {})

    model = os.environ.get("PENPAL_MODEL") or defaults.get("model", DEFAULT_MODEL)
    max_tokens = int(os.environ.get("PENPAL_MAX_TOKENS") or defaults.get("max_tokens", DEFAULT_MAX_TOKENS))
    poll_interval = int(os.environ.get("PENPAL_POLL_INTERVAL") or defaults.get("poll_interval", DEFAULT_POLL_INTERVAL))
    preview_lines = display.get("preview_lines", 100)
    extraction_enabled = extraction.get("enabled", True)
    extraction_min_lines = extraction.get("min_lines", 20)
    extraction_output_dir = Path(extraction.get("output_dir", "."))

    return PenpalConfig(
        model=model,
        max_tokens=max_tokens,
        poll_interval=poll_interval,
        preview_lines=preview_lines,
        extraction_enabled=extraction_enabled,
        extraction_min_lines=extraction_min_lines,
        extraction_output_dir=extraction_output_dir,
        skills_dir=skills_dir(),
        db_path=db_path(),
        config_file=cf,
    )
