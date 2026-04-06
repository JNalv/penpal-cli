"""Token-to-cost calculation using batch API pricing."""
from __future__ import annotations

# Batch API pricing (50% of standard). Per million tokens.
BATCH_PRICING: dict[str, dict[str, float]] = {
    "claude-haiku-4-5-20251001": {"input": 0.40, "output": 2.00},
    "claude-sonnet-4-20250514":  {"input": 1.50, "output": 7.50},
    "claude-opus-4-20250514":    {"input": 7.50, "output": 37.50},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD. Returns 0.0 for unknown models."""
    rates = BATCH_PRICING.get(model)
    if not rates:
        return 0.0
    return (
        (input_tokens * rates["input"] / 1_000_000)
        + (output_tokens * rates["output"] / 1_000_000)
    )


def format_cost(cost: float) -> str:
    """Format a cost value for display."""
    if cost == 0.0:
        return "—"
    if cost < 0.01:
        return f"${cost:.4f}"
    return f"${cost:.2f}"
