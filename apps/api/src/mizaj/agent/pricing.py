"""Date-stamped Anthropic list prices (USD per million tokens)."""

from __future__ import annotations

PRICING_AS_OF = "2026-10-07"

# (input_per_mtok, output_per_mtok) for prompts <= 100K unless noted
PRICES: dict[str, tuple[float, float]] = {
    "claude-haiku-5-5": (0.10, 0.50),
    "claude-haiku-5-5>100k": (0.50, 2.50),
    "claude-sonnet-5-5": (2.00, 10.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    key = model
    if model == "claude-haiku-5-5" and input_tokens > 100_000:
        key = "claude-haiku-5-5>100k"
    inp, out = PRICES.get(key, PRICES["claude-haiku-5-5"])
    return (input_tokens / 1_000_000) * inp + (output_tokens / 1_000_000) * out
