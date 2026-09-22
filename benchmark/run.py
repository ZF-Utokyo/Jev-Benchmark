"""Plan or execute a fresh benchmark collection; historical results are immutable."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sys

from .data import PANEL_SEEDS, PANEL_SHA256, load_panel
from . import protocol, providers


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(2, "Invalid arguments; consult --help. Supplied values are withheld.\n")


def utc():
    return datetime.now(timezone.utc).isoformat()


def jobs(samples, panel, model_key):
    for sample in samples:
        if "anchors" not in sample:
            yield sample, None, None, None
        else:
            for anchor, condition, repeat in protocol.schedule(sample, model_key, PANEL_SEEDS[panel]):
                yield sample, anchor, condition, repeat


def request_parts(sample, anchor, condition):
    if anchor is None:
        return dict(sample["hypotheses"]), None
    visible_ids, requested_ids = protocol.request_layout(sample, anchor, condition)
    return ({key: sample["hypotheses"][key] for key in requested_ids},
            {key: sample["hypotheses"][key] for key in visible_ids})


def result_row(sample, model_key, anchor, condition, repeat, requested, visible, result, adapter):
    primary_ids = list(requested) if anchor is None else [anchor]
    predictions = result["predictions"]
    applicable = adapter != "jev"
    return {
        "stage": "baseline" if anchor is None else "anchor",
        "model_id": model_key, "document_id": str(sample["id"]), "anchor_id": anchor,
        "condition": condition, "repeat": repeat,
        "gold": {key: sample["labels"][key] for key in primary_ids},
        "predictions": {key: predictions[key] for key in primary_ids if key in predictions},
        "valid": result["valid"], "finish_reason": result["finish_reason"],
        "failure_type": result["failure_type"], "client_elapsed_seconds": result["client_elapsed_seconds"],
        "cost_usd": result["cost_usd"],
        "cost_basis": "provider_reported" if result["cost_usd"] is not None else "unknown",
        "usage": result["usage"], "http_status": result["http_status"],
        "requested_ids": list(requested), "visible_ids": list(visible if visible is not None else requested),
        "requested_gold": {key: sample["labels"][key] for key in requested},
        "requested_predictions": predictions,
        "observed_output_order": result["observed_output_order"], "order_applicable": applicable,
        "order_compliant": (result["observed_output_order"] == list(requested)
                            if applicable and result["observed_output_order"] is not None else None),
    }


def write_json(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def collect(args):
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", args.model_key):
        raise ValueError("invalid_model_key")
    if args.max_requests is not None and args.max_requests <= 0:
        raise ValueError("invalid_request_limit")
    config = providers.settings(args.adapter, args.model, reasoning_effort=args.reasoning_effort,
        thinking_level=args.thinking_level, max_output_tokens=args.max_output_tokens,
        temperature=args.temperature, qwen_mode=args.qwen_mode, timeout=args.timeout)
    samples = load_panel(args.data_dir, args.panel)
    scheduled = list(jobs(samples, args.panel, args.model_key))
    expected = len(scheduled)
    # Validate every scientific request before creating a collection or reading a credential.
    for sample, anchor, condition, _repeat in scheduled:
        requested, visible = request_parts(sample, anchor, condition)
        providers.build_payload(sample["contract"], requested, config, visible)
    connection = providers.connection_from_environment(args.adapter) if args.execute else None
    # Refuse both overwrite and implicit continuation of an interrupted run.
    args.output_dir.mkdir(parents=True, exist_ok=False)
    source_hashes = {name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                     for name in ("protocol.py", "data.py", "providers.py", "run.py")}
    manifest = {
        "schema_version": 1, "collection_kind": "new_inference" if args.execute else "offline_plan",
        "historical_result": False, "created_utc": utc(), "panel": args.panel,
        "data_sha256": PANEL_SHA256[args.panel], "model_id": args.model_key,
        "model_configuration": config, "route_kind": args.route_kind,
        "seed_for_schedule_only": PANEL_SEEDS[args.panel], "expected_requests": expected,
        "maximum_attempts": min(expected, args.max_requests or expected),
        "retries": 0, "concurrency_per_model": 1, "request_seed": None,
        "source_sha256": source_hashes,
        "outcome_policy": "invalid and unattempted requests count wrong; no replacement",
        "retention": "parsed labels, allowed resource numbers, and fixed failure categories only",
    }
    write_json(args.output_dir / "run.json", manifest)
    if not args.execute:
        print(json.dumps({"mode": "offline_plan", "expected_requests": expected,
                          "maximum_attempts": manifest["maximum_attempts"], "network_calls": 0}))
        return 0
    attempted = failed = consecutive_failures = 0
    stop = None
    with (args.output_dir / "predictions.jsonl").open("x", encoding="utf-8") as output:
        try:
            for sample, anchor, condition, repeat in scheduled:
                if attempted >= manifest["maximum_attempts"]:
                    stop = "request_limit"
                    break
                requested, visible = request_parts(sample, anchor, condition)
                result = providers.predict(sample["contract"], requested, config, visible=visible, connection=connection)
                row = result_row(sample, args.model_key, anchor, condition, repeat,
                                 requested, visible, result, args.adapter)
                output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
                output.flush()
                os.fsync(output.fileno())
                attempted += 1
                failed += not result["valid"]
                consecutive_failures = 0 if result["valid"] else consecutive_failures + 1
                if result["failure_type"] == "authentication_or_access":
                    stop = "authentication_or_access"
                    break
                if consecutive_failures >= 3:
                    stop = "three_consecutive_failures"
                    break
        except KeyboardInterrupt:
            stop = "interrupted_possible_unrecorded_attempt"
        except Exception:
            # Never persist exception text: transports can include private endpoint information.
            stop = "client_failure_possible_unrecorded_attempt"
    complete = attempted == expected
    write_json(args.output_dir / "completion.json", {
        "completed_utc": utc(), "all_requests_attempted": complete,
        "expected_requests": expected, "recorded_attempts": attempted, "failed_requests": failed,
        "unrecorded_or_unattempted_requests": expected - attempted,
        "stop_reason": stop, "unknown_cost_is_zero": False,
    })
    print(json.dumps({"all_requests_attempted": complete, "recorded_attempts": attempted,
                      "failed_requests": failed, "stop_reason": stop}))
    return 0 if complete else 1


def main(argv=None):
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--panel", choices=tuple(PANEL_SHA256), required=True)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--adapter", choices=providers.ADAPTERS, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--model-key", required=True, help="Short public identifier used for scheduling and reporting")
    parser.add_argument("--output-dir", type=Path, required=True, help="Must not already exist")
    parser.add_argument("--execute", action="store_true", help="Make real, potentially billable inference requests")
    parser.add_argument("--route-kind", choices=("direct", "third_party", "local", "unspecified"), default="unspecified")
    parser.add_argument("--max-requests", type=int, help="Stop early and record incomplete coverage")
    parser.add_argument("--reasoning-effort", choices=("none", "low", "medium", "high"))
    parser.add_argument("--thinking-level", choices=("minimal", "low", "medium", "high", "adaptive", "disabled"))
    parser.add_argument("--max-output-tokens", type=int)
    parser.add_argument("--temperature", type=float)
    parser.add_argument("--qwen-mode", choices=("off", "natural"), default="natural")
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args(argv)
    try:
        return collect(args)
    except (OSError, ValueError, KeyError, TypeError):
        print("Run setup failed; verify arguments, dataset hashes, destination and required environment variables. Details withheld.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
