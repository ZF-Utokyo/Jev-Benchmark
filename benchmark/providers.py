"""Single-attempt provider adapters; only allowlisted parsed outcomes leave memory.

The caller supplies a complete generation endpoint and key through environment
variables. Neither is included in saved results. No redirects, retries, request
seeds, output repairs, model substitutions, or request/response logging are used.
"""

from __future__ import annotations

import math
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from . import protocol

ADAPTERS = ("openai", "openrouter", "gemini", "anthropic", "jev", "qwen")
FINISH_REASONS = {"stop", "length", "content_filter", "tool_calls", "function_call",
                  "STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "OTHER", "BLOCKLIST",
                  "PROHIBITED_CONTENT", "SPII", "MALFORMED_FUNCTION_CALL", "end_turn",
                  "max_tokens", "stop_sequence", "tool_use", "refusal", "pause_turn"}


def settings(adapter, model, *, reasoning_effort=None, thinking_level=None,
             max_output_tokens=None, temperature=None, qwen_mode="natural", timeout=900):
    if adapter not in ADAPTERS or not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", model):
        raise ValueError("invalid_model_configuration")
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("invalid_timeout")
    if max_output_tokens is not None and (type(max_output_tokens) is not int or max_output_tokens <= 0):
        raise ValueError("invalid_output_cap")
    config = {"adapter": adapter, "model": model, "timeout_seconds": timeout}
    if adapter == "jev":
        if any(value is not None for value in (reasoning_effort, thinking_level, max_output_tokens, temperature)):
            raise ValueError("jev_has_no_exposed_decoding_controls")
        return config
    if adapter == "qwen":
        if (qwen_mode not in {"off", "natural"} or
                any(value is not None for value in (reasoning_effort, thinking_level, max_output_tokens, temperature))):
            raise ValueError("qwen_requires_fixed_named_sampling_mode")
        return {**config, "qwen_mode": qwen_mode, "enable_thinking": qwen_mode == "natural",
                "max_output_tokens": 32768 if qwen_mode == "natural" else None,
                "temperature": 1.0 if qwen_mode == "natural" else 0.0,
                "top_p": 0.95 if qwen_mode == "natural" else None}
    if adapter in {"openai", "openrouter"}:
        if thinking_level is not None:
            raise ValueError("unsupported_thinking_setting")
        effort = reasoning_effort or ("none" if "luna" in model else "high" if model in {"gpt-6", "openai/gpt-6-astra"} else "medium")
        if effort not in {"none", "low", "medium", "high"}:
            raise ValueError("invalid_reasoning_effort")
        config["reasoning_effort"] = effort
        config["max_output_tokens"] = max_output_tokens or (8192 if "luna" in model else 16384)
    elif adapter == "gemini":
        if reasoning_effort is not None:
            raise ValueError("unsupported_reasoning_setting")
        thinking = thinking_level or ("minimal" if model == "gemini-3.5-flash-lite" else "low")
        if thinking not in {"minimal", "low", "medium", "high"}:
            raise ValueError("invalid_thinking_level")
        config["thinking_level"] = thinking
        config["max_output_tokens"] = max_output_tokens or 16384
        if model != "gemini-3.5-flash-lite":
            config["temperature"] = 1.0
    elif adapter == "anthropic":
        thinking = thinking_level or ("disabled" if model == "claude-haiku-4-5-20251001" else "adaptive")
        effort = reasoning_effort or ("none" if thinking == "disabled" else "medium")
        if thinking not in {"adaptive", "disabled"} or effort not in {"none", "low", "medium", "high"}:
            raise ValueError("invalid_anthropic_thinking")
        if thinking == "disabled" and effort != "none":
            raise ValueError("disabled_thinking_requires_no_effort")
        if temperature is not None:
            raise ValueError("unsupported_anthropic_sampling_override")
        config.update(thinking_level=thinking, reasoning_effort=effort,
                      max_output_tokens=max_output_tokens or (8192 if thinking == "disabled" else 16384))
    if type(config["max_output_tokens"]) is not int or config["max_output_tokens"] <= 0:
        raise ValueError("invalid_output_cap")
    if temperature is not None:
        if type(temperature) not in (int, float) or not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ValueError("invalid_temperature")
        config["temperature"] = temperature
    return config


def build_payload(contract, requested, config, visible=None):
    adapter, model = config["adapter"], config["model"]
    if adapter == "jev":
        return protocol.jev_payload(contract, requested, model, visible)
    messages = protocol.messages(contract, requested, visible)
    schema = protocol.output_schema(requested)
    if adapter == "gemini":
        generation = {
            "candidateCount": 1, "maxOutputTokens": config["max_output_tokens"],
            "thinkingConfig": {"thinkingLevel": config["thinking_level"], "includeThoughts": False},
            "responseMimeType": "application/json", "responseJsonSchema": schema,
        }
        if "temperature" in config:
            generation["temperature"] = config["temperature"]
        return {"systemInstruction": {"parts": [{"text": messages[0]["content"]}]},
                "contents": [{"role": "user", "parts": [{"text": messages[1]["content"]}]}],
                "generationConfig": generation}
    if adapter == "anthropic":
        output = {"format": {"type": "json_schema", "schema": schema}}
        if config["reasoning_effort"] != "none":
            output["effort"] = config["reasoning_effort"]
        return {"model": model, "system": messages[0]["content"], "messages": messages[1:],
                "stream": False, "thinking": {"type": config["thinking_level"]},
                "max_tokens": config["max_output_tokens"], "output_config": output}
    payload = {"model": model, "messages": messages, "stream": False}
    if adapter == "qwen":
        natural = config["qwen_mode"] == "natural"
        payload.update(temperature=config["temperature"], n=1,
            max_tokens=32768 if natural else (2048 if visible is not None else max(256, 64 * len(requested))),
            chat_template_kwargs={"enable_thinking": natural}, structured_outputs={"json": schema})
        if natural:
            payload.update(top_p=0.95, top_k=-1, min_p=0.0, presence_penalty=0.0,
                frequency_penalty=0.0, repetition_penalty=1.0, min_tokens=0,
                ignore_eos=False, return_token_ids=True)
    else:
        payload.update(max_completion_tokens=config["max_output_tokens"], response_format={
            "type": "json_schema", "json_schema": {"name": "contract_nli_labels", "strict": True, "schema": schema}})
        if adapter == "openrouter":
            payload.update(reasoning={"effort": config["reasoning_effort"]},
                           provider={"require_parameters": True, "allow_fallbacks": False})
        else:
            payload.update(reasoning_effort=config["reasoning_effort"], service_tier="default")
        if "temperature" in config:
            payload["temperature"] = config["temperature"]
    return payload


def _valid_count(value):
    return type(value) is int and value >= 0


def resources(raw, adapter):
    """Drop arbitrary provider text, IDs, nested objects and unspecified currencies."""
    usage = raw.get("usageMetadata" if adapter == "gemini" else "usage")
    usage = usage if isinstance(usage, dict) else {}
    def count(mapping, name):
        value = mapping.get(name) if isinstance(mapping, dict) else None
        return value if _valid_count(value) else None
    selected = {"input_tokens": None, "completion_tokens": None,
                "cached_input_tokens": None, "reasoning_tokens": None}
    if adapter == "gemini":
        selected.update(input_tokens=count(usage, "promptTokenCount"),
                        cached_input_tokens=count(usage, "cachedContentTokenCount"),
                        reasoning_tokens=count(usage, "thoughtsTokenCount"))
        visible, thoughts = count(usage, "candidatesTokenCount"), count(usage, "thoughtsTokenCount")
        if visible is not None and thoughts is not None:
            selected["completion_tokens"] = visible + thoughts
        else:
            total, prompt = count(usage, "totalTokenCount"), count(usage, "promptTokenCount")
            if total is not None and prompt is not None and total >= prompt:
                selected["completion_tokens"] = total - prompt
    elif adapter in {"jev", "anthropic"}:
        selected.update(input_tokens=count(usage, "input_tokens"), completion_tokens=count(usage, "output_tokens"))
        if adapter == "anthropic":
            selected["cached_input_tokens"] = count(usage, "cache_read_input_tokens")
            created = count(usage, "cache_creation_input_tokens")
            # Native Anthropic input_tokens excludes both cache reads and writes.
            if selected["input_tokens"] is not None:
                selected["input_tokens"] += (selected["cached_input_tokens"] or 0) + (created or 0)
            if created is not None:
                selected["cache_creation_input_tokens"] = created
            cache = usage.get("cache_creation")
            for native, normalized in (("ephemeral_5m_input_tokens", "cache_creation_5m_tokens"),
                                       ("ephemeral_1h_input_tokens", "cache_creation_1h_tokens")):
                value = count(cache, native)
                if value is not None:
                    selected[normalized] = value
            detail = usage.get("output_tokens_details")
            selected["reasoning_tokens"] = count(detail, "thinking_tokens")
    else:
        selected.update(input_tokens=count(usage, "prompt_tokens"),
                        completion_tokens=count(usage, "completion_tokens"),
                        cached_input_tokens=count(usage.get("prompt_tokens_details"), "cached_tokens"),
                        reasoning_tokens=count(usage.get("completion_tokens_details"), "reasoning_tokens"))
    cost = usage.get("cost" if adapter == "openrouter" else "cost_usd")
    if type(cost) not in (int, float) or not math.isfinite(cost) or cost < 0:
        cost = None
    if cost is not None:
        selected["reported_cost_usd"] = cost
    finish = raw.get("stop_reason")
    if adapter == "gemini":
        choices = raw.get("candidates")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish = choices[0].get("finishReason")
    elif adapter in {"openai", "openrouter", "qwen"}:
        choices = raw.get("choices")
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            finish = choices[0].get("finish_reason")
    return {"usage": selected, "cost_usd": cost,
            "finish_reason": finish if isinstance(finish, str) and finish in FINISH_REASONS else None}


def _require_counts(raw, names, required=True):
    usage = raw.get("usage")
    if usage is None and not required:
        return
    if not isinstance(usage, dict) or any(not _valid_count(usage.get(name)) for name in names):
        raise ValueError("invalid_usage")


def parse_response(raw, requested, config):
    if not isinstance(raw, dict) or "error" in raw:
        raise ValueError("invalid_response")
    adapter = config["adapter"]
    if adapter == "jev":
        answers = raw.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(requested):
            raise ValueError("invalid_choice_ids")
        _require_counts(raw, ("input_tokens", "output_tokens"))
        if not isinstance(raw.get("model"), str) or not raw["model"]:
            raise ValueError("missing_model")
        labels = {}
        for key in requested:
            answer = answers[key]
            if (not isinstance(answer, dict) or answer.get("type") != "choice"
                    or not isinstance(answer.get("choice"), str) or answer["choice"] not in protocol.LABELS):
                raise ValueError("invalid_choice")
            probabilities, confidence = answer.get("probabilities"), answer.get("confidence")
            if (not isinstance(probabilities, dict) or set(probabilities) != set(protocol.LABELS)
                    or any(type(value) not in (int, float) or not 0 <= value <= 1 for value in probabilities.values())
                    or not math.isclose(sum(probabilities.values()), 1.0, abs_tol=0.02)
                    or type(confidence) not in (int, float) or not 0 <= confidence <= 1):
                raise ValueError("invalid_choice_distribution")
            labels[key] = answer["choice"]
        return labels, list(answers)
    if adapter == "gemini":
        candidates = raw.get("candidates")
        if (not isinstance(candidates, list) or len(candidates) != 1 or
                not isinstance(candidates[0], dict) or candidates[0].get("finishReason") != "STOP"):
            raise ValueError("incomplete_response")
        content = candidates[0].get("content")
        parts = content.get("parts") if isinstance(content, dict) else None
        if not isinstance(parts, list):
            raise ValueError("invalid_content")
        texts = []
        for part in parts:
            if not isinstance(part, dict):
                raise ValueError("invalid_content")
            if part.get("thought"):
                continue
            if "text" in part:
                if not isinstance(part["text"], str):
                    raise ValueError("invalid_content")
                texts.append(part["text"])
            elif any(key != "thoughtSignature" for key in part):
                raise ValueError("invalid_content")
    elif adapter == "anthropic":
        if (raw.get("model") != config["model"] or raw.get("type") != "message"
                or raw.get("role") != "assistant" or raw.get("stop_reason") != "end_turn"
                or raw.get("stop_sequence") is not None):
            raise ValueError("incomplete_or_mismatched_response")
        _require_counts(raw, ("input_tokens", "output_tokens"))
        for name in ("cache_creation_input_tokens", "cache_read_input_tokens"):
            if name in raw["usage"] and not _valid_count(raw["usage"][name]):
                raise ValueError("invalid_usage")
        if raw.get("refusal") or raw.get("tool_calls") or raw.get("function_call"):
            raise ValueError("unexpected_action")
        content, texts = raw.get("content"), []
        if not isinstance(content, list):
            raise ValueError("invalid_content")
        for block in content:
            if not isinstance(block, dict):
                raise ValueError("invalid_content")
            kind = block.get("type")
            field = {"text": "text", "thinking": "thinking", "redacted_thinking": "data"}.get(kind) if isinstance(kind, str) else None
            if field is None or not isinstance(block.get(field), str):
                raise ValueError("invalid_content")
            if kind == "text":
                texts.append(block[field])
    else:
        choices = raw.get("choices")
        if (not isinstance(choices, list) or len(choices) != 1 or
                not isinstance(choices[0], dict) or choices[0].get("finish_reason") != "stop"):
            raise ValueError("incomplete_response")
        message = choices[0].get("message")
        if (not isinstance(message, dict) or not isinstance(message.get("content"), str)
                or message.get("refusal") or message.get("tool_calls") or message.get("function_call")):
            raise ValueError("invalid_content")
        if adapter == "openai" and raw.get("model") != config["model"]:
            raise ValueError("mismatched_model")
        _require_counts(raw, ("prompt_tokens", "completion_tokens", "total_tokens"), required=adapter != "openrouter")
        texts = [message["content"]]
    if not texts:
        raise ValueError("missing_answer")
    return protocol.parse_labels("".join(texts), requested)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def connection_from_environment(adapter):
    endpoint = os.environ.get("BENCHMARK_ENDPOINT", "")
    key = os.environ.get("BENCHMARK_API_KEY", "")
    try:
        parsed = urlsplit(endpoint)
        parsed.port
        valid = (parsed.scheme in {"http", "https"} and bool(parsed.hostname)
                 and parsed.username is None and parsed.password is None
                 and not parsed.query and not parsed.fragment and "?" not in endpoint and "#" not in endpoint
                 and "\\" not in endpoint and endpoint.isascii()
                 and not any(ord(char) < 33 or ord(char) == 127 for char in endpoint))
        if parsed.scheme == "http" and adapter != "qwen":
            valid = False
    except ValueError:
        valid = False
    if not valid or (not key and adapter != "qwen"):
        raise ValueError("invalid_endpoint_or_missing_key")
    if key and (not key.isascii() or not key.isprintable() or any(char.isspace() for char in key)):
        raise ValueError("invalid_key_format")
    return endpoint, key


def predict(contract, requested, config, *, visible=None, connection=None):
    """Return parsed labels/resource numbers or a fixed failure category only."""
    endpoint, key = connection if connection is not None else connection_from_environment(config["adapter"])
    payload = build_payload(contract, requested, config, visible)
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "JevBenchmark/1.0"}
    if key:
        if config["adapter"] == "gemini":
            headers["x-goog-api-key"] = key
        elif config["adapter"] == "anthropic":
            headers["x-api-key"] = key
            headers["anthropic-version"] = "2023-06-01"
        else:
            headers["Authorization"] = "Bearer " + key
    request = Request(endpoint, data=protocol.json_bytes(payload), headers=headers, method="POST")
    result = {"valid": False, "predictions": {}, "usage": None, "cost_usd": None,
              "finish_reason": None, "failure_type": None, "http_status": None,
              "observed_output_order": None}
    started = time.perf_counter()
    try:
        opener = build_opener(_NoRedirect())
        with opener.open(request, timeout=config["timeout_seconds"]) as response:
            body = response.read(16 * 1024 * 1024 + 1)
        if len(body) > 16 * 1024 * 1024:
            raise ValueError("response_size_limit")
        raw = protocol.load_json(body)
        if not isinstance(raw, dict):
            raise ValueError("invalid_response")
        result.update(resources(raw, config["adapter"]))
        labels, order = parse_response(raw, requested, config)
        result.update(valid=True, predictions=labels, observed_output_order=order)
    except HTTPError as error:
        result["http_status"] = error.code
        result["failure_type"] = "authentication_or_access" if error.code in {401, 402, 403} else "http_error"
        error.close()
    except (URLError, TimeoutError, OSError):
        result["failure_type"] = "transport_error"
    except (ValueError, TypeError, KeyError, UnicodeError, OverflowError):
        result["failure_type"] = "invalid_response"
    result["client_elapsed_seconds"] = time.perf_counter() - started
    return result
