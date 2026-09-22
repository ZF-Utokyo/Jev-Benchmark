"""Recompute resource costs from normalized, credential-free usage fields."""
from __future__ import annotations

import json
import math
from pathlib import Path


def finite_nonnegative(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def load_rates(path="configs/pricing.json"):
    return json.loads(Path(path).read_text())["models"]


def cost_for_attempt(row, rates):
    """Return (USD or None, basis); missing resource data never become free calls."""
    model = row["model_id"]
    spec = rates.get(model)
    if spec is None:
        return None, "unknown"
    basis = spec["basis"]
    usage = row.get("usage") or {}
    if basis == "rental_equivalent":
        seconds = row.get("client_elapsed_seconds")
        if not finite_nonnegative(seconds):
            return None, "unknown"
        return seconds * spec["gpus"] * spec["usd_per_gpu_hour"] / 3600, basis
    if basis == "provider_reported":
        value = usage.get("reported_cost_usd")
        return (value, basis) if finite_nonnegative(value) else (None, "unknown")
    inputs, outputs = usage.get("input_tokens"), usage.get("completion_tokens")
    if not finite_nonnegative(inputs):
        return None, "unknown"
    if model == "jev":
        return inputs * spec["input"] / 1e6, basis
    cached = usage.get("cached_input_tokens")
    if not all(finite_nonnegative(x) for x in (outputs, cached)):
        return None, "unknown"
    prefix = "long_context_" if inputs > spec.get("long_context_threshold", math.inf) else ""
    input_rate, output_rate, cache_rate = (spec[prefix + key] for key in ("input", "output", "cached_input"))
    if model.startswith("claude-"):
        five, hour = usage.get("cache_creation_5m_tokens"), usage.get("cache_creation_1h_tokens")
        if not all(finite_nonnegative(x) for x in (five, hour)):
            return None, "unknown"
        cost = inputs * input_rate + cached * cache_rate
        cost += five * spec["cache_creation_5m"] + hour * spec["cache_creation_1h"]
    else:
        if cached > inputs:
            return None, "unknown"
        cost = (inputs - cached) * input_rate + cached * cache_rate
    return (cost + outputs * output_rate) / 1e6, basis


def verify_costs(rows, rates):
    for index, row in enumerate(rows, 1):
        cost, basis = cost_for_attempt(row, rates)
        expected = row.get("cost_usd")
        if (cost is None) != (expected is None):
            raise ValueError(f"Cost coverage differs on row {index}")
        if cost is not None and not math.isclose(cost, expected, rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError(f"Cost differs on row {index}")
        if basis != row.get("cost_basis"):
            raise ValueError(f"Cost basis differs on row {index}")
    return len(rows)
