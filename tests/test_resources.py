import unittest

from benchmark.resources import cost_for_attempt


class ResourceTests(unittest.TestCase):
    def test_unknown_reported_cost_is_not_zero(self):
        self.assertEqual(cost_for_attempt({"model_id": "x", "usage": {}}, {"x": {"basis": "provider_reported"}}), (None, "unknown"))

    def test_gpu_failure_still_costs(self):
        row = {"model_id": "x", "valid": False, "client_elapsed_seconds": 1800}
        self.assertEqual(cost_for_attempt(row, {"x": {"basis": "rental_equivalent", "gpus": 1, "usd_per_gpu_hour": 2}}), (1, "rental_equivalent"))

    def test_cache_is_not_double_counted(self):
        row = {"model_id": "x", "usage": {"input_tokens": 1000000, "completion_tokens": 100000, "cached_input_tokens": 200000}}
        spec = {"x": {"basis": "listed_rate_estimate", "input": 2, "output": 10, "cached_input": 0.2}}
        self.assertAlmostEqual(cost_for_attempt(row, spec)[0], 2.64)

    def test_jev_uses_input_tokens_only(self):
        row = {"model_id": "jev", "usage": {"input_tokens": 1000000, "completion_tokens": None}}
        spec = {"jev": {"basis": "listed_rate_estimate", "input": .042}}
        self.assertEqual(cost_for_attempt(row, spec), (.042, "listed_rate_estimate"))
