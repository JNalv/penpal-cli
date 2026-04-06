"""Constructs Messages API payloads from CLI inputs."""
from __future__ import annotations

import uuid
from typing import Optional

from penpal.config import MODEL_ALIASES


def resolve_model(name: str) -> str:
    """Resolve alias to full model string. Pass through if already full."""
    return MODEL_ALIASES.get(name.lower(), name)


def build_single_request(
    prompt: str,
    model: str,
    max_tokens: int,
    system_prompt: Optional[str] = None,
    custom_id: Optional[str] = None,
) -> dict:
    """Build a single batch request object."""
    if custom_id is None:
        custom_id = f"req-{uuid.uuid4().hex[:8]}"

    params: dict = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system_prompt:
        params["system"] = system_prompt

    return {"custom_id": custom_id, "params": params}
