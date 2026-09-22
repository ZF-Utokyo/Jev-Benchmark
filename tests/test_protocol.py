import hashlib
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from benchmark import protocol, providers, run


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.contract = "A test contract."
        self.requested = {"h2": "Second hypothesis.", "h1": "First hypothesis."}
        self.visible = {"h1": "First hypothesis.", "h2": "Second hypothesis."}
        self.sample = {"id": 42, "contract": self.contract, "hypotheses": self.visible,
                       "anchors": ["h2"], "labels": {"h1": "entailment", "h2": "not_mentioned"}}

    def test_conditions_change_visibility_and_output_order(self):
        expected = {"A": (["h2"], ["h2"]), "B": (["h1", "h2"], ["h2"]),
                    "C": (["h1", "h2"], ["h2", "h1"]), "D": (["h1", "h2"], ["h1", "h2"])}
        inputs = []
        for condition, layout in expected.items():
            self.assertEqual(protocol.request_layout(self.sample, "h2", condition), layout)
            requested, visible = run.request_parts(self.sample, "h2", condition)
            inputs.append(protocol.visible_input_text(self.contract, requested, visible))
        self.assertEqual(len(set(inputs[1:])), 1)
        self.assertNotEqual(inputs[0], inputs[1])

    def test_schedule_contains_twelve_unique_jobs_and_uses_model_key(self):
        first = protocol.schedule(self.sample, "model-a")
        self.assertEqual(first, protocol.schedule(self.sample, "model-a"))
        self.assertEqual(len(set(first)), 12)
        self.assertEqual(set(first), {("h2", c, r) for c in "ABCD" for r in range(3)})
        self.assertNotEqual(first, protocol.schedule(self.sample, "model-b"))

    def test_jev_is_native_choice_and_order_not_temporal(self):
        config = providers.settings("jev", "jev-1.13.0")
        payload = providers.build_payload(self.contract, self.requested, config, self.visible)
        self.assertNotIn("messages", payload)
        self.assertEqual(list(payload["questions"]), ["h2", "h1"])
        self.assertEqual(payload["questions"]["h2"]["type"], "choice")
        self.assertNotIn("Requested output order:", payload["state"])

    def test_frozen_request_body_regressions(self):
        # Hashes were independently derived from the collection-time builders.
        cases = [
            ("jev", "jev-1.13.0", "6d72ee549e2dbe9f3d669a7da25db5e8fbf4a3e68f01d92590e3f22c7b05e0cb", "6d6ce37899792f12ffba639f497d9a33b4101140ae1448e5e997f20265b67c93"),
            ("gemini", "gemini-3.1-pro-preview", "d3e322ef8d3a68233f6f07e02de99332cf268efd1c18fbb6957935a7a5e6feda", "cfcc675cd7de1b861b240be670d8c83e1d247886e1d953af99d98cab870761db"),
            ("gemini", "gemini-3.5-flash-lite", "d9b557f64a537c6806b00f24ffbd8c2e53723222f9d46da08e0a081deac65e0e", "48982f3a7d1b5aef19ef578a7cc1bbb9aac532d4d5ca93cc5425bdc74ab29db3"),
            ("openrouter", "openai/gpt-5.6-luna", "091a8ca837d2742a0c1c6ad7d5b81bcf14a1943c552ddba0148011d6fe94e46b", "39757a5cb98c3dcd5780fc2ec7cce81f0c7e03ac6440baba53f48cb7b411ef02"),
            ("openrouter", "openai/gpt-6-astra", "cbd31aa52a925b38b6ff90bbae1dd43dc75c0b960fcac06f8aa759726936dd24", "d3f8a4f7eb8d9a50cdc1ac31432f9ad10c4d65af6100709fe2520b323dad7d6f"),
            ("openai", "gpt-5.6-terra", "1c2ea2e41cadc31659b715fb37e4ed1a56b323797e737c6e7bd10d3a492f4782", "bc18b0e8db4fa3ca35cc92300128a7db0ecba614a99ae613455c692eaa941915"),
            ("anthropic", "claude-sonnet-5", "c4f9ae079ffa8237dee612135fbee6c7a57e5d32a348f3716cd60d881165863d", "84daf3619d6ef1e5a84eab96e342cc56278b56b7260a5fb87bf9ed9e8872bf78"),
            ("anthropic", "claude-haiku-4-5-20251001", "c04569993704cc4179b9f0a18cba7e7ac5e5ebea8209b96aafc844693a4154e5", "88d8c5dd4b5d5eb4651e22713cb9547732cf0dea0a78bb6434a41f6fa65770d4"),
        ]
        for adapter, model, baseline, controlled in cases:
            for visible, expected in ((None, baseline), (self.visible, controlled)):
                with self.subTest(adapter=adapter, model=model, controlled=visible is not None):
                    payload = providers.build_payload(self.contract, self.requested, providers.settings(adapter, model), visible)
                    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()
                    self.assertEqual(hashlib.sha256(serialized).hexdigest(), expected)
                    self.assertNotIn("seed", payload)

    def test_qwen_natural_has_common_sampling_and_no_reasoning_cutoff(self):
        config = providers.settings("qwen", "Qwen/Qwen3.5-4B")
        payload = providers.build_payload(self.contract, self.requested, config, self.visible)
        self.assertEqual(payload["max_tokens"], 32768)
        self.assertEqual(payload["top_k"], -1)
        self.assertEqual(payload["temperature"], 1.0)
        self.assertNotIn("thinking_token_budget", payload)
        self.assertEqual(hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                         "0424cd554ee813a88e77785ca03d451d7e0d60b1442d89b6529712829b2a47ee")
        off = providers.settings("qwen", "Qwen/Qwen3.5-4B", qwen_mode="off")
        self.assertEqual(providers.build_payload(self.contract, self.requested, off)["max_tokens"], 256)
        self.assertEqual(providers.build_payload(self.contract, self.requested, off, self.visible)["max_tokens"], 2048)

    def test_strict_parser_rejects_repairs_and_duplicate_keys(self):
        invalid = ['```json\n{"labels":{"h1":"entailment","h2":"entailment"}}\n```',
                   '{"labels":{"h1":"entailment","h1":"contradiction","h2":"entailment"}}',
                   '{"labels":{"h1":"entailment"}}',
                   '{"labels":{"h1":"unknown","h2":"entailment"}}',
                   '{"labels":{"h1":"entailment","h2":"entailment"},"extra":1}',
                   '{"labels":{"h1":NaN,"h2":"entailment"}}']
        for text in invalid:
            with self.subTest(text=text), self.assertRaises(ValueError):
                protocol.parse_labels(text, self.requested)

    def test_wrong_key_order_remains_valid_but_is_disclosed(self):
        labels, order = protocol.parse_labels('{"labels":{"h1":"entailment","h2":"not_mentioned"}}', self.requested)
        self.assertEqual(order, ["h1", "h2"])
        result = {"predictions": labels, "valid": True, "finish_reason": "stop", "failure_type": None,
                  "client_elapsed_seconds": 1.0, "cost_usd": None, "usage": None,
                  "http_status": None, "observed_output_order": order}
        row = run.result_row(self.sample, "example", "h2", "C", 0,
                             self.requested, self.visible, result, "openai")
        self.assertTrue(row["valid"])
        self.assertFalse(row["order_compliant"])
        self.assertEqual(row["predictions"], {"h2": "not_mentioned"})
        self.assertEqual(row["requested_predictions"], labels)
        native = run.result_row(self.sample, "example", "h2", "C", 0,
                                self.requested, self.visible, result, "jev")
        self.assertIsNone(native["order_compliant"])

    def test_retention_allowlist_discards_response_text(self):
        marker = "TEST-ONLY-PRIVATE-MARKER"
        raw = {"model": "example-model", "choices": [{"finish_reason": "stop", "message": {
            "content": '{"labels":{"h2":"not_mentioned","h1":"entailment"}}', "reasoning": marker}}],
            "usage": {"prompt_tokens": 12, "completion_tokens": 9, "total_tokens": 21,
                      "private_text": marker, "cost": 99, "completion_tokens_details": {"reasoning_tokens": 2, "text": marker}},
            "private_field": marker}
        body = io.BytesIO(json.dumps(raw).encode())
        class Opener:
            def open(self, request, timeout):
                return body
        with patch.object(providers, "build_opener", return_value=Opener()):
            result = providers.predict(self.contract, self.requested,
                providers.settings("openai", "example-model"),
                connection=("https://example.invalid/generation", marker))
        self.assertTrue(result["valid"])
        self.assertNotIn(marker, json.dumps(result))
        self.assertIsNone(result["cost_usd"])
        self.assertEqual(result["usage"]["reasoning_tokens"], 2)

    def test_http_failure_is_one_attempt_and_no_error_body_retained(self):
        error = HTTPError("https://example.invalid/generation", 401, "withheld", {}, io.BytesIO(b"TEST-ONLY-PRIVATE-MARKER"))
        with patch.object(providers, "build_opener") as factory:
            factory.return_value.open.side_effect = error
            result = providers.predict(self.contract, self.requested, providers.settings("jev", "jev-1.13.0"),
                                       connection=("https://example.invalid/generation", "test-placeholder"))
        self.assertEqual(factory.return_value.open.call_count, 1)
        self.assertEqual(result["failure_type"], "authentication_or_access")
        self.assertNotIn("TEST-ONLY", json.dumps(result))

    def test_truncated_generation_is_invalid(self):
        raw = {"choices": [{"finish_reason": "length", "message": {
            "content": '{"labels":{"h2":"not_mentioned","h1":"entailment"}}'}}]}
        with self.assertRaises(ValueError):
            providers.parse_response(raw, self.requested, providers.settings("openrouter", "example/model"))

    def test_usage_normalization_keeps_combined_output_and_cache_details(self):
        gemini = providers.resources({"usageMetadata": {"promptTokenCount": 100,
            "candidatesTokenCount": 20, "thoughtsTokenCount": 30}}, "gemini")
        self.assertEqual(gemini["usage"]["completion_tokens"], 50)
        self.assertEqual(gemini["usage"]["reasoning_tokens"], 30)
        anthropic = providers.resources({"usage": {"input_tokens": 100, "output_tokens": 20,
            "cache_read_input_tokens": 50, "cache_creation_input_tokens": 40,
            "cache_creation": {"ephemeral_5m_input_tokens": 30, "ephemeral_1h_input_tokens": 10}}}, "anthropic")
        self.assertEqual(anthropic["usage"]["input_tokens"], 190)
        self.assertEqual(anthropic["usage"]["cache_creation_5m_tokens"], 30)
        self.assertEqual(anthropic["usage"]["cached_input_tokens"], 50)
        self.assertIsNone(anthropic["cost_usd"])


if __name__ == "__main__":
    unittest.main()
