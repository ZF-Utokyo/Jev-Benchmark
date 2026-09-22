"""Recompute public metrics offline and optionally check the frozen reference."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from benchmark.metrics import compute_metrics
from benchmark.resources import load_rates, verify_costs


def verify_subset(actual, expected, path="metrics"):
    """Check all frozen reference values; allow additional derived metrics."""
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            raise ValueError(f"{path}: expected an object")
        for key, value in expected.items():
            if key not in actual:
                raise ValueError(f"{path}.{key}: missing reference metric")
            verify_subset(actual[key], value, f"{path}.{key}")
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise ValueError(f"{path}: list length differs")
        for index, value in enumerate(expected):
            verify_subset(actual[index], value, f"{path}[{index}]")
    elif type(expected) in (int, float):
        if type(actual) not in (int, float) or not math.isclose(actual, expected, rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError(f"{path}: computed {actual!r}, expected {expected!r}")
    elif actual != expected:
        raise ValueError(f"{path}: computed {actual!r}, expected {expected!r}")


def write_tables(report, directory):
    """Write portable, numeric CSV tables directly from the reproduced report."""
    baseline_columns = ["model_id", "contracts", "target_judgments", "correct", "failed_requests",
                        "accuracy", "accuracy_ci95_low", "accuracy_ci95_high", "macro_f1",
                        "cost_total_usd", "cost_usd_per_contract", "cost_known_requests", "cost_basis",
                        "median_seconds", "p95_seconds"]
    with (directory / "baseline.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=baseline_columns)
        writer.writeheader()
        for model, item in report["baseline"]["models"].items():
            cost, elapsed = item["resources"]["cost"], item["resources"]["client_elapsed_seconds"]
            interval = item.get("accuracy_ci95", [None, None])
            writer.writerow({"model_id": model, **{key: item[key] for key in
                ("contracts", "target_judgments", "correct", "failed_requests", "accuracy", "macro_f1")},
                "accuracy_ci95_low": interval[0], "accuracy_ci95_high": interval[1],
                "cost_total_usd": cost["total_usd"], "cost_usd_per_contract": cost["usd_per_request"],
                "cost_known_requests": cost["known_requests"], "cost_basis": ";".join(sorted(cost["basis_counts"])),
                "median_seconds": elapsed["median"], "p95_seconds": elapsed["p95"]})
    states = ("all12_correct", "stable_wrong", "changed_valid", "invalid")
    anchor_columns = ["model_id", "targets", "mean_anchor_accuracy", "failed_requests",
                      *states, *(f"{key}_rate" for key in states), "median_seconds", "p95_seconds"]
    with (directory / "anchor.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=anchor_columns)
        writer.writeheader()
        for model, item in report["anchor"]["models"].items():
            correctness, resources = item["correctness_states"], item["resources"]
            writer.writerow({"model_id": model, "targets": correctness["targets"],
                "mean_anchor_accuracy": item["mean_anchor_accuracy"], "failed_requests": resources["failed_requests"],
                **correctness["counts"], **{f"{key}_rate": value for key, value in correctness["rates"].items()},
                "median_seconds": resources["client_elapsed_seconds"]["median"],
                "p95_seconds": resources["client_elapsed_seconds"]["p95"]})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, default=ROOT / "data/predictions.jsonl")
    parser.add_argument("--expected", type=Path, default=ROOT / "data/expected_metrics.json")
    parser.add_argument("--output", type=Path, default=ROOT / "results/metrics.json")
    parser.add_argument("--pricing", type=Path, default=ROOT / "configs/pricing.json")
    parser.add_argument("--bootstrap-draws", type=int, default=5000,
                        help="Whole-contract bootstrap draws (0 skips intervals)")
    parser.add_argument("--seed", type=int, default=20260922)
    parser.add_argument("--check", action="store_true", help="Verify the frozen expected-metrics projection")
    args = parser.parse_args(argv)
    raw = args.predictions.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    report = compute_metrics(rows, bootstrap_draws=args.bootstrap_draws, seed=args.seed, strict_formal=True)
    report["audit"]["predictions_sha256"] = hashlib.sha256(raw).hexdigest()
    if args.check:
        report["audit"]["cost_rows_verified"] = verify_costs(rows, load_rates(args.pricing))
        verify_subset(report, json.loads(args.expected.read_text(encoding="utf-8")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    write_tables(report, args.output.parent)
    print(json.dumps({"status": "verified" if args.check else "reproduced", "models": report["audit"]["models"],
                      "requests": len(rows), "failures": report["audit"]["failed_requests"],
                      "output": args.output.name, "tables": ["baseline.csv", "anchor.csv"]}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        print(f"Reproduction failed: {error}", file=sys.stderr)
        raise SystemExit(1)
