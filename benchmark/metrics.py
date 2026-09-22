"""Offline metrics for the three-class, paired-contract benchmark.

Every planned judgment remains in its accuracy and F1 denominator. An invalid
request contributes no predictions, even if a partially parsed label survived.
Pairwise changes use jointly valid predictions and separately report coverage.
Bootstrap samples contain whole contracts, including every target and repeat.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache
from itertools import combinations
import math
import random
import statistics

LABELS = ("entailment", "contradiction", "not_mentioned")
CONDITIONS = ("A", "B", "C", "D")
REPEATS = (0, 1, 2)
FORMAL_MODELS = frozenset(("jev", "gemini-flash-lite", "gemini-pro", "luna", "terra",
                           "astra", "claude-haiku45", "claude-sonnet5", "qwen4b", "qwen9b"))


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def number(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def quantile(values, probability):
    """Linear interpolation at (n-1)*p, including latency p95."""
    values = sorted(values)
    if not values or not 0 <= probability <= 1:
        raise ValueError("Quantile requires values and a probability in [0, 1]")
    position = (len(values) - 1) * probability
    low, high = math.floor(position), math.ceil(position)
    return values[low] + (position - low) * (values[high] - values[low])


def quality(pairs):
    """Three-class macro-F1; missing labels contribute false negatives."""
    pairs = list(pairs)
    if any(gold not in LABELS or pred not in (*LABELS, None) for gold, pred in pairs):
        raise ValueError("Unknown three-class label")
    correct = sum(gold == pred for gold, pred in pairs)
    valid = sum(pred is not None for _, pred in pairs)
    recalls, f1s = {}, []
    for label in LABELS:
        tp = sum(gold == label and pred == label for gold, pred in pairs)
        fp = sum(gold != label and pred == label for gold, pred in pairs)
        fn = sum(gold == label and pred != label for gold, pred in pairs)
        recalls[label] = ratio(tp, tp + fn)
        f1s.append(ratio(2 * tp, 2 * tp + fp + fn) or 0.0)
    return {"target_judgments": len(pairs), "correct": correct, "valid_predictions": valid,
            "accuracy": ratio(correct, len(pairs)), "macro_f1": statistics.mean(f1s),
            "prediction_coverage": ratio(valid, len(pairs)), "recall_by_class": recalls}


def paired_changes(pairs):
    """Compare (gold, left, right); two missing predictions never agree."""
    counts = Counter(dict.fromkeys(("expected_pairs", "jointly_valid_pairs", "missing_either",
        "baseline_missing", "condition_missing", "flips", "agreements", "correct_to_wrong",
        "wrong_to_correct", "wrong_to_wrong_flips", "both_correct", "both_wrong",
        "baseline_correct", "condition_correct"), 0))
    for gold, left, right in pairs:
        counts["expected_pairs"] += 1
        counts["baseline_correct"] += left == gold
        counts["condition_correct"] += right == gold
        counts["baseline_missing"] += left is None
        counts["condition_missing"] += right is None
        if left is None or right is None:
            counts["missing_either"] += 1
            continue
        counts["jointly_valid_pairs"] += 1
        counts["flips"] += left != right
        counts["agreements"] += left == right
        counts["correct_to_wrong"] += left == gold and right != gold
        counts["wrong_to_correct"] += left != gold and right == gold
        counts["wrong_to_wrong_flips"] += left != gold and right != gold and left != right
        counts["both_correct"] += left == gold and right == gold
        counts["both_wrong"] += left != gold and right != gold
    total, valid = counts["expected_pairs"], counts["jointly_valid_pairs"]
    return {**counts, "prediction_pair_coverage": ratio(valid, total),
            "flip_rate": ratio(counts["flips"], valid),
            "agreement_rate_on_expected": ratio(counts["agreements"], total),
            "baseline_accuracy": ratio(counts["baseline_correct"], total),
            "condition_accuracy": ratio(counts["condition_correct"], total),
            "accuracy_difference": ratio(counts["condition_correct"] - counts["baseline_correct"], total)}


def resource_summary(rows, expected):
    """Recorded client time and known costs include failed attempts."""
    rows = list(rows)
    elapsed = [r["client_elapsed_seconds"] for r in rows if number(r.get("client_elapsed_seconds"))]
    costs = [r["cost_usd"] for r in rows if number(r.get("cost_usd"))]
    tokens = [(r.get("usage") or {}).get("completion_tokens") for r in rows]
    tokens = [value for value in tokens if type(value) is int and value >= 0]
    total_cost = sum(costs) if len(costs) == expected else None
    return {"requests": len(rows), "expected_requests": expected,
            "failed_requests": sum(not r["valid"] for r in rows),
            "missing_requests": expected - len(rows), "failed_requests_included": True,
            "client_elapsed_seconds": {"known_requests": len(elapsed),
                "total": sum(elapsed) if len(elapsed) == expected else None,
                "mean": statistics.mean(elapsed) if elapsed else None,
                "median": statistics.median(elapsed) if elapsed else None,
                "p95": quantile(elapsed, .95) if elapsed else None},
            "cost": {"total_usd": total_cost,
                "known_subtotal_usd": sum(costs) if costs else None,
                "known_requests": len(costs), "unknown_requests": expected - len(costs),
                "basis_counts": dict(Counter(r.get("cost_basis", "unknown") for r in rows)),
                "usd_per_request": total_cost / expected if total_cost is not None and expected else None},
            "completion_tokens": {"known_requests": len(tokens), "unknown_requests": expected - len(tokens),
                "known_subtotal": sum(tokens), "total": sum(tokens) if len(tokens) == expected else None,
                "mean_observed": statistics.mean(tokens) if tokens else None}}


@lru_cache(maxsize=8)
def _bootstrap_draws(clusters, draws, seed):
    rng = random.Random(seed)
    return tuple(tuple(rng.randrange(clusters) for _ in range(clusters)) for _ in range(draws))


def paired_interval(left, right, denominator, *, draws=5000, seed=20260922):
    """Right-minus-left contrast, with paired whole-contract resampling."""
    if not left or set(left) != set(right) or denominator <= 0 or draws < 1:
        raise ValueError("Paired bootstrap requires matching nonempty contract panels")
    differences = [right[doc] - left[doc] for doc in left]
    values = [sum(differences[i] for i in selected) / denominator
              for selected in _bootstrap_draws(len(left), draws, seed)]
    return {"difference": sum(differences) / denominator,
            "ci95": [quantile(values, .025), quantile(values, .975)],
            "contract_clusters": len(left), "draws": draws, "seed": seed,
            "method": "paired whole-contract percentile bootstrap, linear interpolation; descriptive, unadjusted"}


def _rate_intervals(documents, denominators, *, draws, seed):
    """Historical anchor intervals use the lower empirical percentile index."""
    rows = list(documents.values())
    result = {}
    for name, denominator in denominators.items():
        numerators = [row[name] for row in rows]
        totals = [row[denominator] for row in rows]
        values = sorted(sum(numerators[i] for i in draw) / sum(totals[i] for i in draw)
                        for draw in _bootstrap_draws(len(rows), draws, seed))
        result[name] = {"estimate": sum(numerators) / sum(totals),
                        "ci95": [values[int(.025 * (draws - 1))], values[int(.975 * (draws - 1))]],
                        "documents": len(rows), "draws": draws, "valid_draws": draws,
                        "undefined_draws": 0, "seed": seed}
    return result


def _prediction(row, target):
    return row["predictions"].get(target) if row and row["valid"] else None


def _index(rows):
    """Validate prediction records and construct the shared planned panels."""
    records, baseline_gold, anchor_gold, models = {}, {}, {}, []
    for row in rows:
        stage, model, doc = (row.get(k) for k in ("stage", "model_id", "document_id"))
        if stage not in ("baseline", "anchor") or not isinstance(model, str) or not isinstance(doc, str):
            raise ValueError("Invalid stage, model, or document identifier")
        if not model or not doc or type(row.get("valid")) is not bool:
            raise ValueError("Empty identifier or non-Boolean validity")
        gold, predictions = row.get("gold"), row.get("predictions")
        if not isinstance(gold, dict) or not gold or any(x not in LABELS for x in gold.values()):
            raise ValueError("Gold must map target IDs to the three benchmark classes")
        if not isinstance(predictions, dict) or any(x not in LABELS for x in predictions.values()):
            raise ValueError("Predictions must contain only parsed benchmark labels")
        if set(predictions) - set(gold) or (row["valid"] and set(predictions) != set(gold)):
            raise ValueError("A valid request must predict every and only requested target")
        for field in ("client_elapsed_seconds", "cost_usd"):
            if row.get(field) is not None and not number(row[field]):
                raise ValueError("Resource fields must be nonnegative finite numbers or null")
        if model not in models:
            models.append(model)
        if stage == "baseline":
            if any(row.get(k) is not None for k in ("anchor_id", "condition", "repeat")):
                raise ValueError("Baseline rows cannot carry anchor coordinates")
            key = stage, model, doc
            if doc in baseline_gold and baseline_gold[doc] != gold:
                raise ValueError("Gold labels differ across baseline models")
            baseline_gold[doc] = gold
        else:
            anchor, condition, repeat = (row.get(k) for k in ("anchor_id", "condition", "repeat"))
            if not isinstance(anchor, str) or set(gold) != {anchor} or condition not in CONDITIONS:
                raise ValueError("Anchor rows require a singleton gold label and condition A/B/C/D")
            if type(repeat) is not int or repeat not in REPEATS:
                raise ValueError("Anchor repeat must be 0, 1, or 2")
            key = stage, model, doc, anchor, condition, repeat
            unit = doc, anchor
            if unit in anchor_gold and anchor_gold[unit] != gold[anchor]:
                raise ValueError("Gold labels differ across anchor attempts")
            anchor_gold[unit] = gold[anchor]
        if key in records:
            raise ValueError("Duplicate planned attempt")
        records[key] = row
    for (doc, anchor), label in anchor_gold.items():
        if doc in baseline_gold and baseline_gold[doc].get(anchor) != label:
            raise ValueError("Anchor gold differs from the corresponding baseline target")
    return records, baseline_gold, anchor_gold, models


def compute_metrics(rows, *, bootstrap_draws=5000, seed=20260922, strict_formal=False):
    """Compute metrics using shared planned panels, including absent attempts.

    The released JSONL contains every planned attempt, including failures.
    ``strict_formal`` additionally enforces the formal ten-model 123x17 and
    30x4x3 panels. Smaller synthetic panels are accepted by the library default.
    Input order preserves the frozen contract order for historical bootstraps.
    """
    rows = list(rows)
    if type(bootstrap_draws) is not int or bootstrap_draws < 0:
        raise ValueError("Bootstrap draws must be a nonnegative integer")
    records, baseline_gold, anchor_gold, models = _index(rows)
    if not rows:
        raise ValueError("No prediction records")
    if strict_formal:
        if set(models) != FORMAL_MODELS or len(baseline_gold) != 123 or any(len(g) != 17 for g in baseline_gold.values()):
            raise ValueError("Expected ten formal models and 123 contracts with 17 baseline targets")
        if len(anchor_gold) != 30 or len({doc for doc, _ in anchor_gold}) != 30:
            raise ValueError("Expected 30 anchor targets in 30 contracts")
        for model in models:
            for doc in baseline_gold:
                if ("baseline", model, doc) not in records:
                    raise ValueError("Missing planned baseline attempt")
            for doc, anchor in anchor_gold:
                for condition in CONDITIONS:
                    for repeat in REPEATS:
                        if ("anchor", model, doc, anchor, condition, repeat) not in records:
                            raise ValueError("Missing planned anchor attempt")
    report = {"schema_version": 1, "labels": list(LABELS),
              "baseline": {"models": {}}, "anchor": {"models": {}},
              "audit": {"recorded_requests": len(rows), "failed_requests": sum(not r["valid"] for r in rows),
                        "models": len(models), "formal_panel": strict_formal},
              "bootstrap": {"draws": bootstrap_draws, "seed": seed, "unit": "whole contract",
                            "anchor_percentile": "lower empirical index", "paired_percentile": "linear interpolation"}}
    baseline_vectors, anchor_vectors, condition_vectors = {}, {}, {}
    by_stage_model = defaultdict(list)
    for row in rows:
        by_stage_model[row["stage"], row["model_id"]].append(row)
    for model in models:
        if baseline_gold:
            pairs, vector = [], {}
            for doc, gold in baseline_gold.items():
                row = records.get(("baseline", model, doc))
                doc_pairs = [(label, _prediction(row, target)) for target, label in gold.items()]
                pairs.extend(doc_pairs)
                vector[doc] = sum(g == p for g, p in doc_pairs)
            actual = by_stage_model["baseline", model]
            item = {**quality(pairs), "contracts": len(baseline_gold), "recorded_requests": len(actual),
                    "valid_requests": sum(r["valid"] for r in actual),
                    "failed_requests": sum(not r["valid"] for r in actual),
                    "missing_requests": len(baseline_gold) - len(actual),
                    "resources": resource_summary(actual, len(baseline_gold))}
            if bootstrap_draws:
                zeros = dict.fromkeys(vector, 0)
                item["accuracy_ci95"] = paired_interval(zeros, vector, len(pairs), draws=bootstrap_draws, seed=seed)["ci95"]
            report["baseline"]["models"][model] = item
            baseline_vectors[model] = vector
        if not anchor_gold:
            continue
        conditions, transitions, condition_vectors[model] = {}, {}, {}
        for condition in CONDITIONS:
            pairs, repeat_pairs, doc_correct = [], [], dict.fromkeys(dict.fromkeys(d for d, _ in anchor_gold), 0)
            for (doc, anchor), gold in anchor_gold.items():
                predictions = [_prediction(records.get(("anchor", model, doc, anchor, condition, repeat)), anchor)
                               for repeat in REPEATS]
                pairs.extend((gold, pred) for pred in predictions)
                repeat_pairs.extend((gold, predictions[a], predictions[b]) for a, b in combinations(REPEATS, 2))
                doc_correct[doc] += sum(pred == gold for pred in predictions)
            actual = [r for r in by_stage_model["anchor", model] if r["condition"] == condition]
            conditions[condition] = {"quality": quality(pairs), "repeat_disagreement": paired_changes(repeat_pairs),
                                     "resources": resource_summary(actual, len(pairs))}
            condition_vectors[model][condition] = doc_correct
        for left, right in zip(CONDITIONS, CONDITIONS[1:]):
            pairs = [(gold,
                      _prediction(records.get(("anchor", model, doc, anchor, left, repeat)), anchor),
                      _prediction(records.get(("anchor", model, doc, anchor, right, repeat)), anchor))
                     for (doc, anchor), gold in anchor_gold.items() for repeat in REPEATS]
            transitions[f"{left}_to_{right}"] = paired_changes(pairs)
        robust, av = _robustness(records, model, anchor_gold, bootstrap_draws, seed)
        counts = {"all12_correct": robust["all_twelve_correct"], "stable_wrong": robust["stable_wrong"],
                  "changed_valid": robust["all_twelve_complete"] - robust["strict_stable"],
                  "invalid": len(anchor_gold) - robust["all_twelve_complete"]}
        report["anchor"]["models"][model] = {
            "conditions": conditions, "transitions": transitions, "robustness": robust,
            "correctness_states": {"counts": counts, "rates": {k: v / len(anchor_gold) for k, v in counts.items()},
                                   "targets": len(anchor_gold)},
            "mean_anchor_accuracy": statistics.mean(c["quality"]["accuracy"] for c in conditions.values()),
            "resources": resource_summary(by_stage_model["anchor", model], len(anchor_gold) * 12)}
        anchor_vectors[model] = av
    if bootstrap_draws:
        options = {"draws": bootstrap_draws, "seed": seed}
        if "jev" in baseline_vectors:
            denominator = sum(map(len, baseline_gold.values()))
            report["baseline"]["paired_differences_from_jev"] = {
                model: paired_interval(baseline_vectors["jev"], vector, denominator, **options)
                for model, vector in baseline_vectors.items() if model != "jev"}
        if "jev" in anchor_vectors:
            report["anchor"]["paired_all12_differences_from_jev"] = {
                model: paired_interval(anchor_vectors["jev"], vector, len(anchor_gold), **options)
                for model, vector in anchor_vectors.items() if model != "jev"}
        report["anchor"]["paired_condition_differences"] = {
            model: {f"{left}_to_{right}": paired_interval(vectors[left], vectors[right], len(anchor_gold) * 3, **options)
                    for left, right in zip(CONDITIONS, CONDITIONS[1:])}
            for model, vectors in condition_vectors.items()}
    return report


def _robustness(records, model, anchor_gold, draws, seed):
    names = ("anchor_units", "anchor_repeat_units", "all_four_complete", "all_four_correct",
             "all_twelve_complete", "all_twelve_correct", "strict_stable", "stable_correct", "stable_wrong")
    docs = dict.fromkeys(doc for doc, _ in anchor_gold)
    per_doc = {doc: Counter(dict.fromkeys(names, 0)) for doc in docs}
    repeats = {str(repeat): {doc: Counter(dict.fromkeys(("anchor_units", "all_four_complete", "all_four_correct"), 0))
                            for doc in docs} for repeat in REPEATS}
    for (doc, anchor), gold in anchor_gold.items():
        matrix = [[_prediction(records.get(("anchor", model, doc, anchor, condition, repeat)), anchor)
                   for condition in CONDITIONS] for repeat in REPEATS]
        flat = [pred for row in matrix for pred in row]
        complete = all(pred is not None for pred in flat)
        stable = complete and len(set(flat)) == 1
        correct = all(pred == gold for pred in flat)
        count = per_doc[doc]
        count["anchor_units"] += 1
        count["anchor_repeat_units"] += 3
        count["all_twelve_complete"] += complete
        count["all_twelve_correct"] += correct
        count["strict_stable"] += stable
        count["stable_correct"] += stable and correct
        count["stable_wrong"] += stable and not correct
        for repeat, values in enumerate(matrix):
            all_complete, all_correct = all(v is not None for v in values), all(v == gold for v in values)
            count["all_four_complete"] += all_complete
            count["all_four_correct"] += all_correct
            repeats[str(repeat)][doc]["anchor_units"] += 1
            repeats[str(repeat)][doc]["all_four_complete"] += all_complete
            repeats[str(repeat)][doc]["all_four_correct"] += all_correct
    sums = {name: sum(count[name] for count in per_doc.values()) for name in names}
    denominators = {name: "anchor_repeat_units" if name.startswith("all_four") else "anchor_units"
                    for name in names[2:]}
    result = {"documents": len(docs), **sums, "rates": {name: sums[name] / sums[d] for name, d in denominators.items()},
              "denominators": denominators, "per_document": per_doc, "per_repeat": {}}
    for repeat, documents in repeats.items():
        counts = {name: sum(c[name] for c in documents.values()) for name in ("anchor_units", "all_four_complete", "all_four_correct")}
        result["per_repeat"][repeat] = {**counts,
            "all_four_correct_rate": counts["all_four_correct"] / sums["anchor_units"],
            "all_four_complete_rate": counts["all_four_complete"] / sums["anchor_units"], "per_document": documents}
        if draws:
            result["per_repeat"][repeat]["intervals"] = _rate_intervals(documents,
                {name: "anchor_units" for name in ("all_four_correct", "all_four_complete")}, draws=draws, seed=seed)
    if draws:
        result["intervals"] = _rate_intervals(per_doc, denominators, draws=draws, seed=seed)
    return result, {doc: counts["all_twelve_correct"] for doc, counts in per_doc.items()}
