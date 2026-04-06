"""Manages reusable system prompt markdown files in ~/.config/penpal/skills/."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def _skill_path(skills_dir: Path, name: str) -> Path:
    return skills_dir / f"{name}.md"


def list_skills(skills_dir: Path) -> list[tuple[str, str]]:
    """Return sorted list of (name, description) pairs."""
    results = []
    for md_file in sorted(skills_dir.glob("*.md")):
        name = md_file.stem
        description = _extract_description(md_file)
        results.append((name, description))
    return results


def _extract_description(md_file: Path) -> str:
    """Extract description from first # heading line, or return '(no description)'."""
    try:
        for line in md_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
    except OSError:
        pass
    return "(no description)"


def get_skill(skills_dir: Path, name: str) -> Optional[str]:
    """Return skill content or None if not found."""
    path = _skill_path(skills_dir, name)
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def skill_exists(skills_dir: Path, name: str) -> bool:
    return _skill_path(skills_dir, name).exists()


def delete_skill(skills_dir: Path, name: str) -> bool:
    """Delete skill file. Returns True if deleted, False if not found."""
    path = _skill_path(skills_dir, name)
    if not path.exists():
        return False
    path.unlink()
    return True


def skill_path(skills_dir: Path, name: str) -> Path:
    return _skill_path(skills_dir, name)
