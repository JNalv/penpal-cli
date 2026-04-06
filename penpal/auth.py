"""API key storage and retrieval via keyring with file fallback."""
from __future__ import annotations

import os
import stat
from pathlib import Path

import keyring
import keyring.errors

from penpal.config import credentials_file

KEYRING_SERVICE = "penpal"
KEYRING_USERNAME = "anthropic_api_key"


class AuthError(Exception):
    pass


def _file_creds_path() -> Path:
    return credentials_file()


def _store_in_file(key: str) -> None:
    path = _file_creds_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(key)
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _read_from_file() -> str | None:
    path = _file_creds_path()
    if path.exists():
        return path.read_text().strip() or None
    return None


def store_api_key(key: str) -> str:
    """Store the API key. Returns 'keyring' or 'file' indicating storage method."""
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key)
        return "keyring"
    except (keyring.errors.NoKeyringError, Exception):
        _store_in_file(key)
        return "file"


def get_api_key() -> str:
    """Retrieve stored API key. Raises AuthError if not configured."""
    # Env var takes precedence
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key

    # Try keyring
    try:
        key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if key:
            return key
    except (keyring.errors.NoKeyringError, Exception):
        pass

    # Try file fallback
    key = _read_from_file()
    if key:
        return key

    raise AuthError(
        "No API key configured. Run `penpal auth` or set ANTHROPIC_API_KEY."
    )


def delete_api_key() -> bool:
    """Remove the stored API key. Returns True if something was deleted."""
    deleted = False
    try:
        existing = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
        if existing:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
            deleted = True
    except (keyring.errors.NoKeyringError, Exception):
        pass

    path = _file_creds_path()
    if path.exists():
        path.unlink()
        deleted = True

    return deleted


def get_key_status() -> dict:
    """Return info about the stored key without revealing it."""
    env_key = os.environ.get("ANTHROPIC_API_KEY")

    keyring_key = None
    try:
        keyring_key = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
    except (keyring.errors.NoKeyringError, Exception):
        pass

    file_key = _read_from_file()

    active_key = env_key or keyring_key or file_key

    def mask(k: str | None) -> str:
        if not k:
            return "(not set)"
        return k[:12] + "..." + k[-4:]

    return {
        "env_var": mask(env_key) if env_key else "(not set)",
        "keyring": mask(keyring_key) if keyring_key else "(not set)",
        "file": mask(file_key) if file_key else "(not set)",
        "active": mask(active_key) if active_key else "(not set)",
        "source": "env" if env_key else ("keyring" if keyring_key else ("file" if file_key else "none")),
    }
