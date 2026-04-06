"""Constructs Messages API payloads from CLI inputs."""
from __future__ import annotations

import base64
import mimetypes
import uuid
from pathlib import Path
from typing import Optional

from penpal.config import MODEL_ALIASES

# Supported file types
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
PDF_EXTENSIONS = {".pdf"}
TEXT_EXTENSIONS = {
    ".txt", ".csv", ".tsv", ".md", ".html", ".json", ".xml",
    ".yaml", ".yml", ".py", ".js", ".ts", ".java", ".c", ".cpp",
    ".rs", ".go", ".rb", ".sh", ".sql", ".r", ".swift", ".kt",
    ".log", ".rtf",
}

MAX_IMAGE_SIZE = 5 * 1024 * 1024   # 5 MB
MAX_PDF_SIZE = 32 * 1024 * 1024    # 32 MB
MAX_TEXT_SIZE = 512 * 1024          # 512 KB


def resolve_model(name: str) -> str:
    """Resolve alias to full model string. Pass through if already full."""
    return MODEL_ALIASES.get(name.lower(), name)


def build_file_content_block(file_path: Path) -> tuple[str | None, dict]:
    """
    Build a content block for the given file.
    Returns (text_prefix, content_block) where text_prefix is non-None only for
    text files (to be prepended to the user prompt string).
    Raises ValueError for unsupported or oversized files.
    """
    suffix = file_path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        data = file_path.read_bytes()
        if len(data) > MAX_IMAGE_SIZE:
            raise ValueError(
                f"Image '{file_path.name}' is {len(data) / 1024 / 1024:.1f} MB "
                f"(max 5 MB)."
            )
        media_type, _ = mimetypes.guess_type(str(file_path))
        if not media_type:
            media_type = "image/jpeg"
        encoded = base64.standard_b64encode(data).decode()
        return (None, {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": encoded,
            },
        })

    elif suffix in PDF_EXTENSIONS:
        data = file_path.read_bytes()
        if len(data) > MAX_PDF_SIZE:
            raise ValueError(
                f"PDF '{file_path.name}' is {len(data) / 1024 / 1024:.1f} MB "
                f"(max 32 MB)."
            )
        encoded = base64.standard_b64encode(data).decode()
        return (None, {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": encoded,
            },
            "title": file_path.name,
        })

    elif suffix in TEXT_EXTENSIONS:
        data = file_path.read_bytes()
        if len(data) > MAX_TEXT_SIZE:
            raise ValueError(
                f"Text file '{file_path.name}' is {len(data) / 1024:.1f} KB "
                f"(max 512 KB)."
            )
        text = data.decode("utf-8", errors="replace")
        size_str = f"{len(data) / 1024:.1f} KB"
        prefix = (
            f"--- Attached file: {file_path.name} ({size_str}) ---\n"
            f"{text}\n"
            f"--- End of attachment ---\n\n"
        )
        return (prefix, {})  # Empty dict signals text file (no block needed)

    else:
        supported = sorted(IMAGE_EXTENSIONS | PDF_EXTENSIONS | TEXT_EXTENSIONS)
        raise ValueError(
            f"Unsupported file type '{suffix}'. Supported: {', '.join(supported)}"
        )


def build_batch_requests(
    template_prompt: str,
    files: list[Path],
    model: str,
    max_tokens: int,
    system_prompt: Optional[str] = None,
) -> list[dict]:
    """Build one batch request per file, applying template_prompt to each."""
    requests = []
    for fp in files:
        requests.append(
            build_single_request(
                prompt=template_prompt,
                model=model,
                max_tokens=max_tokens,
                system_prompt=system_prompt,
                custom_id=fp.name,
                files=[fp],
            )
        )
    return requests


def build_single_request(
    prompt: str,
    model: str,
    max_tokens: int,
    system_prompt: Optional[str] = None,
    custom_id: Optional[str] = None,
    files: Optional[list[Path]] = None,
) -> dict:
    """Build a single batch request object."""
    if custom_id is None:
        custom_id = f"req-{uuid.uuid4().hex[:8]}"

    # Build content blocks
    content: list[dict] | str
    text_prefixes: list[str] = []
    content_blocks: list[dict] = []

    for fp in (files or []):
        text_prefix, block = build_file_content_block(fp)
        if text_prefix is not None:
            text_prefixes.append(text_prefix)
        else:
            content_blocks.append(block)

    full_prompt = "".join(text_prefixes) + prompt

    if content_blocks:
        # Mixed content: blocks first, then the text prompt
        content_blocks.append({"type": "text", "text": full_prompt})
        content = content_blocks
    else:
        content = full_prompt

    params: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": content}],
    }
    if system_prompt:
        params["system"] = system_prompt

    return {"custom_id": custom_id, "params": params}
