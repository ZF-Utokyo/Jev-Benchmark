"""Synthetic checks for failure denominators and paired stability semantics."""
import unittest

from analysis.reproduce import verify_subset
from benchmark.metrics import (compute_metrics, paired_changes, paired_interval,
                               quality, quantile, resource_summary)


E, C, N = "entailment", "contradiction", "not_mentioned"


def anchor_row(doc, condition, repeat, prediction=E, *, valid=True, model="example"):
    return {"stage": "anchor", "model_id": model, "document_id": doc, "anchor_id": "h1",
            "condition": condition, "repeat": repeat, "gold": {"h1": E},
            "predictions": {"h1": prediction} if prediction else {}, "valid": valid,
            "client_elapsed_seconds": 1.0, "cost_usd": .01,
            "cost_basis": "listed_rate_estimate", "usage": {"completion_tokens": 10}}


class MetricsTests(unittest.TestCase):
    def test_missing_judgment_remains_in_accuracy_and_f1(self):
        score = quality([(E, E), (C, C), (N, None)])
        self.assertEqual(score["target_judgments"], 3)
        self.assertEqual(score["correct"], 2)
        self.assertAlmostEqual(score["accuracy"], 2 / 3)
        self.assertAlmostEqual(score["macro_f1"], 2 / 3)
        self.assertEqual(score["recall_by_class"][N], 0)

    def test_pair_changes_separate_correction_regression_and_wrong_flip(self):
        score = paired_changes([(E, C, E), (E, E, N), (E, C, N), (E, None, None), (E, None, E)])
        self.assertEqual(score["expected_pairs"], 5)
        self.assertEqual(score["jointly_valid_pairs"], 3)
        self.assertEqual(score["flips"], 3)
        self.assertEqual(score["wrong_to_correct"], 1)
        self.assertEqual(score["correct_to_wrong"], 1)
        self.assertEqual(score["wrong_to_wrong_flips"], 1)
        self.assertEqual(score["agreements"], 0)
        self.assertAlmostEqual(score["prediction_pair_coverage"], .6)
        self.assertEqual(score["flip_rate"], 1)
        self.assertAlmostEqual(score["accuracy_difference"], .2)

    def test_stability_partition_and_invalid_precedence(self):
        rows = []
        for doc, pred in (("correct", E), ("wrong", C), ("changed", E), ("invalid", C)):
            rows.extend(anchor_row(doc, c, r, pred) for c in "ABCD" for r in range(3))
        changed = next(r for r in rows if r["document_id"] == "changed")
        changed["predictions"]["h1"] = N
        invalid = next(r for r in rows if r["document_id"] == "invalid")
        invalid["valid"] = False  # Even a surviving parsed label is excluded.
        model = compute_metrics(rows, bootstrap_draws=0)["anchor"]["models"]["example"]
        self.assertEqual(model["correctness_states"]["counts"],
                         {"all12_correct": 1, "stable_wrong": 1, "changed_valid": 1, "invalid": 1})
        repeat = model["conditions"]["A"]["repeat_disagreement"]
        self.assertEqual(repeat["expected_pairs"], 12)
        self.assertEqual(repeat["jointly_valid_pairs"], 10)
        self.assertEqual(repeat["flips"], 2)
        self.assertEqual(model["resources"]["failed_requests"], 1)

    def test_absent_anchor_attempt_stays_in_planned_denominator(self):
        rows = [anchor_row("d", c, r) for c in "ABCD" for r in range(3)]
        rows.pop()
        model = compute_metrics(rows, bootstrap_draws=0)["anchor"]["models"]["example"]
        self.assertEqual(model["conditions"]["D"]["quality"]["accuracy"], 2 / 3)
        self.assertEqual(model["correctness_states"]["counts"]["invalid"], 1)
        self.assertEqual(model["resources"]["missing_requests"], 1)

    def test_invalid_baseline_discards_partial_predictions(self):
        row = {"stage": "baseline", "model_id": "example", "document_id": "d",
               "gold": {"h1": E, "h2": C, "h3": N}, "predictions": {"h1": E}, "valid": False}
        model = compute_metrics([row], bootstrap_draws=0)["baseline"]["models"]["example"]
        self.assertEqual(model["target_judgments"], 3)
        self.assertEqual(model["correct"], 0)
        self.assertEqual(model["macro_f1"], 0)

    def test_failed_attempts_are_included_in_resource_summaries(self):
        rows = [anchor_row("a", "A", 0), anchor_row("b", "A", 0, None, valid=False)]
        rows[1].update(client_elapsed_seconds=9.0, cost_usd=None, cost_basis="unknown")
        summary = resource_summary(rows, 2)
        self.assertEqual(summary["client_elapsed_seconds"]["median"], 5)
        self.assertEqual(summary["client_elapsed_seconds"]["p95"], 8.6)
        self.assertIsNone(summary["cost"]["total_usd"])
        self.assertEqual(summary["cost"]["known_subtotal_usd"], .01)
        self.assertEqual(summary["cost"]["known_requests"], 1)

    def test_contract_bootstrap_preserves_target_clustering(self):
        interval = paired_interval({"a": 0, "b": 0}, {"a": 17, "b": 0}, 34, draws=200, seed=7)
        self.assertEqual(interval["difference"], .5)
        self.assertEqual(interval["ci95"], [0, 1])
        self.assertEqual(interval["contract_clusters"], 2)
        with self.assertRaises(ValueError):
            paired_interval({"a": 1}, {"b": 1}, 1)

    def test_duplicate_and_unknown_labels_are_rejected(self):
        row = anchor_row("d", "A", 0)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            compute_metrics([row, row], bootstrap_draws=0)
        with self.assertRaises(ValueError):
            quality([(E, "yes")])

    def test_reference_check_detects_omitted_or_changed_metrics(self):
        verify_subset({"a": 1, "extra": 2}, {"a": 1})
        with self.assertRaises(ValueError):
            verify_subset({"a": 1}, {"a": 2})
        with self.assertRaises(ValueError):
            verify_subset({}, {"a": 1})


if __name__ == "__main__":
    unittest.main()
