#!/usr/bin/env python3
"""Plot the core official-test results from offline-recomputed metrics."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL_LABELS = {
    "jev": "Jev 1.13.0",
    "gemini-flash-lite": "Gemini 3.5 Flash-Lite",
    "gemini-pro": "Gemini 3.1 Pro Preview",
    "luna": "GPT-5.6 Luna",
    "terra": "GPT-5.6 Terra",
    "astra": "GPT-6 Astra",
    "claude-haiku45": "Claude Haiku 4.5",
    "claude-sonnet5": "Claude Sonnet 5",
    "qwen4b": "Qwen3.5-4B",
    "qwen9b": "Qwen3.5-9B",
}
# Family colors are paired with marker shapes and direct model labels.
STYLES = {
    "jev": ("#0072B2", "o"),
    "gemini-flash-lite": ("#9C6B16", "s"),
    "gemini-pro": ("#9C6B16", "s"),
    "luna": ("#555555", "^"),
    "terra": ("#555555", "^"),
    "astra": ("#555555", "^"),
    "claude-haiku45": ("#008767", "D"),
    "claude-sonnet5": ("#008767", "D"),
    "qwen4b": ("#D55E00", "P"),
    "qwen9b": ("#D55E00", "P"),
}
COST_NOTE = (
    "Costs combine reported API charges, token-price estimates, and GPU rental "
    "equivalents at $2.00 per GPU-hour."
)


def positive_number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be finite and positive")
    return float(value)


def collect_points(metrics: dict) -> list[dict]:
    baseline = metrics["baseline"]["models"]
    anchors = metrics["anchor"]["models"]
    if set(baseline) != set(MODEL_LABELS) or set(anchors) != set(MODEL_LABELS):
        raise ValueError("Core release figures require the complete ten-model test comparison")
    points = []
    for key, name in MODEL_LABELS.items():
        base, anchor = baseline[key], anchors[key]
        states = anchor["correctness_states"]
        if base["contracts"] != 123 or base["target_judgments"] != 2091:
            raise ValueError(f"{key}: baseline must contain 123 contracts and 2,091 judgments")
        if states["targets"] != 30 or sum(states["counts"].values()) != 30:
            raise ValueError(f"{key}: anchor outcomes must partition 30 targets")
        accuracy = base["accuracy"]
        low, high = base["accuracy_ci95"]
        if not 0 <= low <= accuracy <= high <= 1:
            raise ValueError(f"{key}: invalid accuracy or interval")
        correct = base["correct"]
        if not math.isclose(accuracy, correct / 2091, rel_tol=0, abs_tol=1e-12):
            raise ValueError(f"{key}: inconsistent accuracy denominator")
        cost = base["resources"]["cost"]
        if (base["resources"]["expected_requests"] != 123
                or cost["known_requests"] != 123 or cost["unknown_requests"] != 0):
            raise ValueError(f"{key}: all 123 baseline requests need known costs")
        dollars = positive_number(cost["usd_per_request"], f"{key}: cost")
        if not math.isclose(cost["total_usd"], dollars * 123, rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError(f"{key}: cost must cover all baseline requests")
        timing = base["resources"]["client_elapsed_seconds"]
        median = positive_number(timing["median"], f"{key}: median response time")
        p95 = positive_number(timing["p95"], f"{key}: P95 response time")
        if median > p95:
            raise ValueError(f"{key}: median exceeds P95")
        all12 = states["counts"]["all12_correct"]
        if not isinstance(all12, int) or not 0 <= all12 <= 30:
            raise ValueError(f"{key}: invalid all-twelve-correct count")
        points.append({
            "model": key,
            "name": name,
            "accuracy": accuracy,
            "accuracy_ci95": [low, high],
            "correct": correct,
            "judgments": 2091,
            "cost_per_contract_usd": dollars,
            "cost_basis_counts": cost["basis_counts"],
            "all12_correct": all12,
            "anchor_targets": 30,
            "median_response_seconds": median,
            "p95_response_seconds": p95,
        })
    return points


def frontier(points: list[dict]) -> list[dict]:
    """Return nondominated measured configurations, ordered by ascending cost."""
    return sorted([
        point for point in points if not any(
            other["cost_per_contract_usd"] <= point["cost_per_contract_usd"]
            and other["accuracy"] >= point["accuracy"]
            and (other["cost_per_contract_usd"] < point["cost_per_contract_usd"]
                 or other["accuracy"] > point["accuracy"])
            for other in points
        )
    ], key=lambda point: point["cost_per_contract_usd"])


def save_figure(fig, output: Path, stem: str, caption: str) -> None:
    # Suppress wall-clock timestamps so exports are portable and repeatable.
    metadata = {
        "pdf": {"Creator": "Jev Benchmark", "CreationDate": None, "ModDate": None},
        "svg": {"Creator": "Jev Benchmark", "Date": None},
        "png": {"Software": "Jev Benchmark"},
    }
    for extension in ("pdf", "svg", "png"):
        fig.savefig(output / f"{stem}.{extension}", dpi=220, bbox_inches="tight",
                    metadata=metadata[extension])
    (output / f"{stem}_caption.txt").write_text(caption + "\n", encoding="utf-8")


def plot_cost_accuracy(points: list[dict], output: Path) -> None:
    from matplotlib import pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

    fig, ax = plt.subplots(figsize=(8.2, 5.4))
    fig.subplots_adjust(left=.10, right=.96, top=.88, bottom=.24)
    observed = frontier(points)
    ax.plot([p["cost_per_contract_usd"] for p in observed],
            [100 * p["accuracy"] for p in observed],
            color="#777777", linestyle=(0, (2, 3)), linewidth=1,
            label="Observed cost–accuracy frontier", zorder=1)
    offsets = {
        "jev": (0, -23, "center"),
        "gemini-flash-lite": (-6, 26, "center"),
        "gemini-pro": (-9, 34, "right"),
        "luna": (0, -23, "center"),
        "terra": (15, 20, "left"),
        "astra": (0, 30, "center"),
        "claude-haiku45": (0, -22, "center"),
        "claude-sonnet5": (14, -20, "left"),
        "qwen4b": (-4, -25, "right"),
        "qwen9b": (4, -27, "left"),
    }
    for point in points:
        key = point["model"]
        color, marker = STYLES[key]
        accuracy = 100 * point["accuracy"]
        ax.scatter(point["cost_per_contract_usd"], accuracy, marker=marker,
                   color=color, s=38, edgecolor="white", linewidth=.5, zorder=3)
        dx, dy, align = offsets[key]
        label = point["name"].replace("Gemini 3.5 ", "Gemini 3.5\n").replace(
            "Gemini 3.1 Pro Preview", "Gemini 3.1 Pro\nPreview")
        ax.annotate(label, (point["cost_per_contract_usd"], accuracy),
                    xytext=(dx, dy), textcoords="offset points", ha=align,
                    va="center", fontsize=8.5, linespacing=1.15)
    ax.set_xscale("log")
    costs = [p["cost_per_contract_usd"] for p in points]
    ax.set_xlim(min(costs) / 1.8, max(costs) * 2.0)
    # Broad five-point ticks; point coordinates are never displaced for layout.
    low = min(p["accuracy"] * 100 for p in points)
    high = max(p["accuracy"] * 100 for p in points)
    ymin = 5 * math.floor((low - 4) / 5)
    ymax = 5 * math.ceil((high + 3) / 5)
    ax.set_ylim(max(0, ymin), min(100, ymax))
    ax.set_yticks(range(max(0, ymin), min(100, ymax) + 1, 5))
    ticks = [multiple * 10 ** exponent for exponent in range(-6, 2)
             for multiple in (1, 2, 5)
             if min(costs) / 1.8 <= multiple * 10 ** exponent <= max(costs) * 2]
    ax.xaxis.set_major_locator(FixedLocator(ticks))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"${value:g}"))
    ax.xaxis.set_minor_locator(NullLocator())
    ax.set_xlabel("Cost per contract (USD, log scale)")
    ax.set_ylabel("Baseline accuracy (%)")
    ax.grid(axis="y", color="#E3E6E8", linewidth=.6, zorder=0)
    ax.legend(loc="lower right", frameon=False, fontsize=8.5)
    fig.text(.10, .96, "123 test contracts · 2,091 judgments per model", fontsize=10,
             va="top")
    fig.text(.10, .08, "Point estimates shown; descriptive 95% intervals are available in the metric data.",
             fontsize=8, va="bottom")
    fig.text(.10, .04, "Cost: reported charges, token-price estimates, or GPU rental equivalents ($2/GPU-hour).",
             fontsize=8, va="bottom")
    low_cost = min(points, key=lambda p: p["cost_per_contract_usd"])
    high_accuracy = max(points, key=lambda p: p["accuracy"])
    caption = (
        f"{low_cost['name']} has the lowest recorded baseline cost, while "
        f"{high_accuracy['name']} has the highest accuracy point estimate. "
        "The baseline contains 123 official-test contracts and 2,091 intended judgments per model; "
        "invalid responses count as incorrect. Descriptive 95% percentile intervals from "
        "5,000 whole-contract bootstrap resamples are retained in the accompanying metric "
        "data and are not displayed here. "
        + COST_NOTE + " The dotted frontier connects nondominated point estimates; "
        "its segments are not evaluated intermediate configurations or significance claims."
    )
    save_figure(fig, output, "cost_accuracy", caption)
    plt.close(fig)


def plot_correctness_time(points: list[dict], output: Path) -> None:
    from matplotlib import pyplot as plt
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator

    fig, axes = plt.subplots(1, 2, figsize=(8.2, 4.6), sharey=True,
                             gridspec_kw={"width_ratios": [1, 1.15]})
    fig.subplots_adjust(left=.28, right=.97, top=.82, bottom=.23, wspace=.16)
    left, right = axes
    positions = list(range(len(points)))
    for position, point in zip(positions, points):
        color, marker = STYLES[point["model"]]
        count = point["all12_correct"]
        left.barh(position, count, height=.53, color=color, alpha=.85)
        left.text(count + .6, position, f"{count}/30", va="center", fontsize=8.5)
        seconds = point["median_response_seconds"]
        right.scatter(seconds, position, color=color, marker=marker, s=30, zorder=3)
        right.annotate(f"{seconds:.2f}", (seconds, position), xytext=(7, 0),
                       textcoords="offset points", va="center", fontsize=8.5)
    left.set_yticks(positions, [point["name"] for point in points], fontsize=8.5)
    left.invert_yaxis()
    left.set_xlim(0, 30)
    left.set_xticks([0, 10, 20, 30])
    left.set_xlabel("All 12 correct (targets)")
    left.set_title("30 anchors · 12 responses each", fontsize=9, pad=12)
    right.set_xscale("log")
    times = [point["median_response_seconds"] for point in points]
    right.set_xlim(min(times) / 1.6, max(times) * 3.1)
    ticks = [multiple * 10 ** exponent for exponent in range(-2, 5)
             for multiple in (1, 3)
             if min(times) / 1.6 <= multiple * 10 ** exponent <= max(times) * 3.1]
    right.xaxis.set_major_locator(FixedLocator(ticks))
    right.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}"))
    right.xaxis.set_minor_locator(NullLocator())
    right.set_xlabel("Median response time (s, log scale)")
    right.set_title("Baseline · 123 attempts", fontsize=9, pad=12)
    right.tick_params(axis="y", left=False)
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#E3E6E8", linewidth=.6)
        ax.spines["left"].set_visible(False)
    left.tick_params(axis="y", length=0, pad=7)
    fig.text(.025, .96, "Correctness across conditions and baseline response time", fontsize=10,
             va="top")
    fig.text(.025, .08, "All 12 correct requires the correct label in every condition and repeat.",
             fontsize=8, va="bottom")
    fig.text(.025, .04, "Time includes all attempts and network/service overhead; it does not isolate model computation.",
             fontsize=8, va="bottom")
    most_correct = max(points, key=lambda point: point["all12_correct"])
    fastest = min(points, key=lambda point: point["median_response_seconds"])
    caption = (
        f"{most_correct['name']} has the largest all-twelve-correct count, and "
        f"{fastest['name']} has the lowest median baseline response time in these configurations. "
        "Left: anchors correct in all four conditions and three repeats, out of 30 targets; "
        "an invalid response prevents a target from qualifying. Right: median client elapsed "
        "time for 123 baseline requests, including failed attempts. Baseline timing and anchor "
        "correctness use different workloads and target sets. Times include network and service "
        "overhead; small count differences do not establish a general stability advantage."
    )
    save_figure(fig, output, "correctness_response_time", caption)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metrics", type=Path, default=ROOT / "results/metrics.json")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results/figures")
    args = parser.parse_args()
    source = args.metrics.read_bytes()
    points = collect_points(json.loads(source))
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "pdf.fonttype": 42, "svg.fonttype": "path", "svg.hashsalt": "jev-benchmark",
    })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    plot_cost_accuracy(points, args.output_dir)
    plot_correctness_time(points, args.output_dir)
    manifest = {
        "schema_version": 1,
        "metrics_sha256": hashlib.sha256(source).hexdigest(),
        "points": points,
        "frontier": [point["model"] for point in frontier(points)],
        "cost_note": COST_NOTE,
        "figures": ["cost_accuracy", "correctness_response_time"],
    }
    (args.output_dir / "plotted_values.json").write_text(
        json.dumps(manifest, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("Wrote core figures and plotted_values.json")


if __name__ == "__main__":
    main()
