"""Extract fenced code blocks from response text and write them to disk."""
from __future__ import annotations

import re
from pathlib import Path

LANG_EXT: dict[str, str] = {
    "python": ".py",
    "javascript": ".js",
    "typescript": ".ts",
    "bash": ".sh",
    "sh": ".sh",
    "rust": ".rs",
    "go": ".go",
    "java": ".java",
    "cpp": ".cpp",
    "c": ".c",
    "html": ".html",
    "css": ".css",
    "json": ".json",
    "yaml": ".yml",
    "toml": ".toml",
    "sql": ".sql",
}

# Regex patterns for filename hints in the first line of a code block
_HINT_PATTERNS = [
    re.compile(r"#\s*filename:\s*(\S+)"),
    re.compile(r"#\s*save\s+as:\s*(\S+)"),
    re.compile(r"//\s*filename:\s*(\S+)"),
    re.compile(r"//\s*save\s+as:\s*(\S+)"),
    re.compile(r"<!--\s*filename:\s*(\S+)\s*-->"),
]

_FENCE_RE = re.compile(r"```(\w+)\n(.*?)```", re.DOTALL)


def _parse_filename_hint(first_line: str) -> str | None:
    for pattern in _HINT_PATTERNS:
        m = pattern.search(first_line)
        if m:
            return m.group(1).strip()
    return None


def extract_code_blocks(
    content: str,
    output_dir: Path,
    min_lines: int = 20,
) -> tuple[str, list[Path]]:
    """
    Scan *content* for fenced code blocks and extract qualifying ones to disk.

    A block qualifies if it has a language identifier AND either:
    - its first line contains a filename hint, OR
    - its line count is >= min_lines

    Returns (modified_content, written_paths).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    counter = 0

    def _replace(m: re.Match) -> str:
        nonlocal counter
        lang = m.group(1).lower()
        body = m.group(2)
        lines = body.splitlines()

        first_line = lines[0] if lines else ""
        hint = _parse_filename_hint(first_line)
        qualifies = hint is not None or len(lines) >= min_lines

        if not qualifies:
            return m.group(0)  # leave unchanged

        if hint:
            filename = hint
        else:
            ext = LANG_EXT.get(lang, f".{lang}")
            counter += 1
            filename = f"response_{counter}{ext}"

        dest = output_dir / filename
        dest.write_text(body, encoding="utf-8")
        written.append(dest)

        return f"[📎 Saved: {filename} ({len(lines)} lines)]"

    modified = _FENCE_RE.sub(_replace, content)
    return modified, written
