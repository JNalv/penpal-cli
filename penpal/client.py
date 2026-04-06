"""All Anthropic Batch API interactions."""
from __future__ import annotations

import time
from typing import Optional

import anthropic

from penpal.models import BatchResult


class APIError(Exception):
    pass


class AuthAPIError(APIError):
    pass


class BillingError(APIError):
    pass


def _make_client(api_key: str) -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=api_key)


def _extract_text(result) -> Optional[str]:
    """Extract text content from a batch result."""
    if result.result.type != "succeeded":
        return None
    content = result.result.message.content
    parts = []
    for block in content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts) if parts else ""


def _with_retry(fn, max_attempts: int = 3):
    """Retry fn on 429/5xx with exponential backoff."""
    delay = 2.0
    for attempt in range(max_attempts):
        try:
            return fn()
        except anthropic.RateLimitError:
            if attempt == max_attempts - 1:
                raise APIError("Rate limit exceeded after retries. Please try again later.")
            time.sleep(delay)
            delay *= 2
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                if attempt == max_attempts - 1:
                    raise APIError(f"Anthropic server error ({e.status_code}): {e.message}")
                time.sleep(delay)
                delay *= 2
            else:
                raise


def submit_batch(api_key: str, requests: list[dict]) -> dict:
    """Submit a batch. Returns dict with 'batch_id' and 'expires_at' (ISO string)."""
    client = _make_client(api_key)

    # Validate key and billing errors immediately — don't retry these.
    def _submit():
        try:
            batch = client.messages.batches.create(requests=requests)
            expires = batch.expires_at.isoformat() if batch.expires_at else None
            return {"batch_id": batch.id, "expires_at": expires}
        except anthropic.AuthenticationError as e:
            raise AuthAPIError(
                f"Invalid API key (401). Run `penpal auth` to reconfigure.\n{e.message}"
            )
        except anthropic.BadRequestError as e:
            msg = e.message or str(e)
            if "credit balance" in msg.lower():
                raise BillingError(
                    "Insufficient credit balance. Add credits at https://console.anthropic.com/settings/billing"
                )
            raise APIError(f"Bad request (400): {msg}")

    return _with_retry(_submit, max_attempts=3)


def check_batch(api_key: str, batch_id: str) -> dict:
    """Check batch status. Returns dict with status and counts."""
    client = _make_client(api_key)

    def _check():
        try:
            batch = client.messages.batches.retrieve(batch_id)
            expires = batch.expires_at.isoformat() if batch.expires_at else None
            return {
                "status": batch.processing_status,  # "in_progress" | "ended"
                "expires_at": expires,
                "counts": {
                    "processing": batch.request_counts.processing,
                    "succeeded": batch.request_counts.succeeded,
                    "errored": batch.request_counts.errored,
                    "canceled": batch.request_counts.canceled,
                    "expired": batch.request_counts.expired,
                },
            }
        except anthropic.AuthenticationError as e:
            raise AuthAPIError(f"Invalid API key: {e.message}")

    return _with_retry(_check)


def get_results(api_key: str, batch_id: str) -> list[BatchResult]:
    """Retrieve all results from a completed batch."""
    client = _make_client(api_key)

    def _fetch():
        try:
            results = []
            for result in client.messages.batches.results(batch_id):
                rtype = result.result.type
                content = _extract_text(result) if rtype == "succeeded" else None
                input_tokens = None
                output_tokens = None
                error = None
                if rtype == "succeeded":
                    usage = result.result.message.usage
                    input_tokens = usage.input_tokens
                    output_tokens = usage.output_tokens
                elif rtype == "errored":
                    error = str(result.result.error)
                results.append(BatchResult(
                    custom_id=result.custom_id,
                    status=rtype,
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    error=error,
                ))
            return results
        except anthropic.AuthenticationError as e:
            raise AuthAPIError(f"Invalid API key: {e.message}")

    return _with_retry(_fetch)


def validate_api_key(api_key: str) -> bool:
    """Validate an API key by making a minimal API call. Raises AuthAPIError on failure."""
    client = _make_client(api_key)
    try:
        # Minimal call to verify the key works
        client.models.list()
        return True
    except anthropic.AuthenticationError:
        raise AuthAPIError("API key is invalid or has been revoked.")
    except anthropic.PermissionDeniedError:
        raise AuthAPIError("API key does not have permission for this operation.")
