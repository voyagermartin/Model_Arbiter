"""core/pricer.py - Official Gemini pricing catalog & precision TWD cost calculator."""

from typing import Dict, Any

# Official USD rates per 1,000,000 tokens
PRICING_CATALOG_USD: Dict[str, Dict[str, float]] = {
    "gemini-3.5-flash-lite": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
        "thought_per_1m": 0.30,
    },
    "gemini-2.5-flash": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "thought_per_1m": 0.40,
    },
    "gemini-2.0-flash": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "thought_per_1m": 0.40,
    },
    "gemini-2.0-flash-lite": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
        "thought_per_1m": 0.30,
    },
    "gemini-1.5-flash": {
        "input_per_1m": 0.075,
        "output_per_1m": 0.30,
        "thought_per_1m": 0.30,
    },
    "gemini-1.5-pro": {
        "input_per_1m": 1.25,
        "output_per_1m": 5.00,
        "thought_per_1m": 5.00,
    },
    "gemini-2.5-pro": {
        "input_per_1m": 1.25,
        "output_per_1m": 5.00,
        "thought_per_1m": 5.00,
    },
    "default": {
        "input_per_1m": 0.10,
        "output_per_1m": 0.40,
        "thought_per_1m": 0.40,
    }
}

DEFAULT_EXCHANGE_RATE_TWD = 32.0


def get_model_pricing(model_name: str) -> Dict[str, float]:
    """Retrieve pricing rates for a given model name, normalized."""
    normalized_name = model_name.lower().replace("models/", "")
    for key in PRICING_CATALOG_USD:
        if key in normalized_name:
            return PRICING_CATALOG_USD[key]
    return PRICING_CATALOG_USD["default"]


def calculate_cost_ntd(
    model_name: str,
    prompt_tokens: int,
    candidate_tokens: int,
    thought_tokens: int = 0,
    exchange_rate: float = DEFAULT_EXCHANGE_RATE_TWD
) -> float:
    """
    Calculates cost in New Taiwan Dollars (TWD/NTD) based on token consumption.
    """
    rates = get_model_pricing(model_name)

    input_cost_usd = (prompt_tokens / 1_000_000.0) * rates["input_per_1m"]
    output_cost_usd = (candidate_tokens / 1_000_000.0) * rates["output_per_1m"]
    thought_cost_usd = (thought_tokens / 1_000_000.0) * rates["thought_per_1m"]

    total_cost_usd = input_cost_usd + output_cost_usd + thought_cost_usd
    total_cost_twd = total_cost_usd * exchange_rate

    return round(total_cost_twd, 6)
