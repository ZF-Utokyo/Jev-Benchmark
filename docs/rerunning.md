# Running a new collection

Python 3.10 or later is sufficient for data preparation and inference; these
modules use only the standard library. New runs are separate from the archived
results. A successful rerun is not a promise of identical answers, latency,
pricing, provider routing, backend revisions, or model availability.

## Prepare the official data

```sh
python -m benchmark.data --output-dir data
```

This downloads the [official ContractNLI ZIP](https://stanfordnlp.github.io/contract-nli/resources/contract-nli.zip),
checks its SHA-256 and the member SHA-256, and writes `test123` and
`test_anchor30` directories. Each contains `input_data.jsonl` and `manifest.json`.
If you already generated these files, use them directly; preparation
refuses to overwrite existing panels. Contract texts are obtained from the
official archive rather than bundled in this release. For offline preparation, pass
`--archive contract-nli.zip`. To reproduce the optional development panels,
add `--include-development`.

Archive SHA-256:
`e03fc77bbf8b53e2976a250e81d8a294bc3d5e5fb014521e477dee9340d6287b`.

The test baseline sorts all 123 contracts by integer ID. The anchor panel samples
30 contracts with Python `random.Random(20260922)`, then samples one hypothesis
per contract using the first eight SHA-256 bytes of
`20260922:anchors:{document_id}` as a big-endian integer seed. Hypothesis order
is the official JSON insertion order. Selection never reads labels to choose
contracts or anchors. Prepared JSONL bytes must match the pinned historical
panel hashes. Text is not truncated or rewritten. The optional development
panels use seeds 20260920 and 20260921 and are not pooled with test data.

## Inspect an offline plan

```sh
python -m benchmark.run --panel test123 --data-dir data \
  --adapter jev --model jev-1.13.0 --model-key jev \
  --route-kind direct --output-dir runs/jev-baseline-plan
```

Without `--execute`, the runner validates all request bodies and writes only a
new `run.json` plan. It does not read credentials or make network calls. The
baseline has 123 requests and 2,091 labels. `--panel test_anchor30` has 360
requests: A/B/C/D × three repetitions × 30 anchors. The short `--model-key`
participates in the deterministic within-document schedule; use the archived
key when comparing request order. Scheduling seeds are never sent as model
sampling seeds.

## Execute with user-supplied connection settings

Set these two variables in your process environment using your own credential
manager or a secure interactive mechanism:

| Variable | Meaning |
| --- | --- |
| `BENCHMARK_ENDPOINT` | Complete generation URL, including the API path. No suffix is appended. For Gemini, include the selected model in the URL. |
| `BENCHMARK_API_KEY` | Your API key. Optional only for a Qwen service configured without authentication. |

Use a complete Chat Completions URL for `openai`, `openrouter`, and `qwen`;
a GenerateContent URL for `gemini`; a Messages URL for `anthropic`; and the
native SystemOne URL for `jev`. The runner requires HTTPS except for a
user-supplied Qwen endpoint. Redirects are refused. Connection settings and
authentication values stay in memory and are never included in artifacts.

Then run the same command with `--execute` and a fresh output directory:

```sh
python -m benchmark.run --panel test_anchor30 --data-dir data \
  --adapter jev --model jev-1.13.0 --model-key jev \
  --route-kind direct --output-dir runs/jev-anchor-new --execute
```

This makes real, potentially billable requests. No inference is part of the
test suite or offline plan. Use provider-side spending controls where needed.
`--max-requests` can cap attempts, but yields an explicitly incomplete
collection and does not change the full benchmark denominator.

## Adapters and sampling

The release preserves collection-time baseline/control prompt wording and
native output interfaces. `configs/models.json` describes historical model
configurations; it does not supply live endpoints or credentials. The runner
uses its named adapter and explicit CLI flags, not that archival file.

| Adapter/configuration | Default decoding and interface |
| --- | --- |
| `jev` | Native Choice questions and criteria; no exposed decoding budget |
| `gemini`, `gemini-3.5-flash-lite` | Minimal thinking, 16,384 output tokens, sampling temperature omitted |
| `gemini`, `gemini-3.1-pro-preview` | Low thinking, temperature 1, 16,384 output tokens |
| `openrouter`, `openai/gpt-5.6-luna` | None reasoning, 8,192 completion tokens; fallback disabled |
| `openrouter`, `openai/gpt-6-astra` | High reasoning, 16,384 completion tokens; fallback disabled |
| `openai`, `gpt-5.6-terra` | Medium reasoning, 16,384 completion tokens, default service tier |
| `openai`, `gpt-6` | High reasoning, 16,384 completion tokens, default service tier |
| `anthropic`, `claude-sonnet-5` | Adaptive thinking, medium effort, 16,384 output tokens |
| `anthropic`, `claude-haiku-4-5-20251001` | Disabled thinking, no effort setting, 8,192 output tokens |
| `qwen`, `--qwen-mode natural` | Thinking enabled, 32,768 combined tokens, temperature 1, top_p .95, top_k -1, min_p 0; no separate reasoning cutoff |
| `qwen`, `--qwen-mode off` | Thinking disabled, temperature 0; baseline cap max(256, 64 × requested hypotheses), controlled cap 2,048 |

Qwen natural mode additionally fixes presence/frequency penalties to 0,
repetition penalty to 1, min_tokens to 0, and ignore_eos to false. It uses the
native chat template switch and `structured_outputs.json`; the serving backend
must support these fields and parse native reasoning. Provision enough context
for the full input plus output allowance and record backend/checkpoint/hardware
details separately. The package does not provision a GPU server or validate
backend equivalence. Natural mode is the fixed common-parameter configuration,
not the full vendor-recommended Qwen sampling recipe.

For compatible generation adapters, explicit `--reasoning-effort`,
`--thinking-level`, `--max-output-tokens`, and `--temperature` override applicable
defaults and appear in the new run manifest. Jev and Qwen reject unsupported
overrides. Token caps include reasoning and final output where the API uses a
combined budget. The timeout defaults to 900 seconds and is separately recorded;
it can be set with `--timeout` (for example 1800 for a slower local service).
Changes are new configurations, not edits to historical results. A generic
adapter does not verify model availability, alias equivalence, or compute parity.

## Outcomes and failure handling

The runner performs one request at a time, never retries or repairs output,
and stops on authentication/access failure or three consecutive failed calls.
JSON must contain exactly the requested labels, with valid class names and no
duplicate keys, markdown wrapping, or extra fields. Abnormal completion is a
failure even if a complete-looking label object appears. Generation key order
is recorded without reordering the observed evidence. Jev C/D change native
question serialization order; they do not establish temporal output order.

`predictions.jsonl` retains only parsed class labels, dataset IDs, fixed failure
categories, recognized finish reasons, numeric usage, measured client elapsed
time, and order-compliance metadata. For an anchor request, `gold` and
`predictions` contain only the anchor; `requested_gold` and
`requested_predictions` retain parsed secondary labels. There are no saved
request bodies, raw responses, reasoning text, exception messages, connection
settings, or authentication values. Only explicitly USD-denominated provider
costs (or OpenRouter's documented USD cost field) are retained; unavailable
charges remain null. Local GPU expenditure is not inferred as zero.
Usage is normalized to a flat numeric map: `input_tokens`, `completion_tokens`
(including reported Gemini thinking), `cached_input_tokens`, and
`reasoning_tokens`; unknown counts are null. Native cache-write breakdowns and
`reported_cost_usd` are retained when provided. Anthropic total input includes
its separately reported cache reads and writes. `cost_basis` is
`provider_reported` or `unknown` for a new run.

`completion.json` records attempted and remaining requests. Invalid and
unattempted requests count wrong in fixed-denominator reporting. A crash or
interrupt may leave an unknown in-flight attempt; such a collection is not
complete. Automatic resume is intentionally unsupported: reconcile it before
any separately identified future collection. Existing directories are never
reused, overwritten, or implicitly resumed.

Run offline checks with:

```sh
python -m unittest discover -s tests
```
