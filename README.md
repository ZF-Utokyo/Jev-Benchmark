# Jev Benchmark

Evaluation code and sanitized prediction records for comparing Jev and nine
language models on the classification component of ContractNLI. The included
records cover the official test baseline and the controlled test-anchor panel.
They support offline recomputation of the core accuracy, correctness, cost,
and response-time results.

## Reproduce the recorded results

Use Python 3.10 or later. From the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m analysis.reproduce --check
python -m analysis.figures
python -m unittest discover -s tests
```

After dependencies are installed, the analysis and plotting commands run
offline and make no model calls. The analysis reads `data/predictions.jsonl`,
checks the frozen reference in `data/expected_metrics.json`, and writes
`results/metrics.json`, `results/baseline.csv`, and `results/anchor.csv`.
The `--check` command also independently recomputes
request costs from sanitized usage, elapsed time, and the recorded price
snapshots. Plotting writes PDF, SVG, and PNG figures plus captions
to `results/figures/`:

- `cost_accuracy`: baseline cost versus accuracy; descriptive 95% intervals
  remain in the metric data.
- `correctness_response_time`: all-twelve-correct anchor counts and median
  baseline response times.

These are portable views of the core results. The package does not claim to
recreate every appendix table, diagnostic, or the paper's exact figure layout.

## Run a new evaluation

[Rerunning instructions](docs/rerunning.md) explain dataset preparation,
adapters, explicit inference settings, and endpoint configuration. The runner
first produces an offline request plan; sending requests requires `--execute`.
Keep new outputs separate from the frozen records.

```sh
python -m benchmark.data --output-dir data
python -m benchmark.run --panel test123 --data-dir data \
  --adapter openai --model YOUR_MODEL_ID --model-key new-model \
  --output-dir runs/new-model
```

Preparing data downloads the upstream archive unless an existing archive is
provided. A new evaluation requires an available model endpoint and can incur
charges. The package configures neither model hosting nor credentials.
Recomputing the recorded results is deterministic; new hosted-model responses
may differ because models, providers, and serving configurations can change.

## Evaluation scope

The baseline contains 123 contracts with 17 judgments each: 2,091 intended
predictions per model. The stability panel contains one fixed anchor from each
of 30 test contracts, four request conditions, and three repeats, for 360
requests per model. Invalid requests count as incorrect and remain in cost and
response-time summaries. All twelve correct means that a target is correct
under every condition and repeat; it is not agreement alone.

Costs combine reported API charges, token-price estimates, and local GPU
rental-equivalent estimates at $2.00 per GPU-hour. Response time is measured
client elapsed time, including network and service overhead. Neither measure
isolates model computation. See the [protocol](docs/protocol.md) for definitions,
uncertainty, inference-setting differences, and interpretation limits.

## Repository contents

| Path | Purpose |
| --- | --- |
| `data/` | Sanitized frozen records and reference metrics |
| `analysis/` | Offline scoring, verification, and plotting |
| `benchmark/` | Dataset preparation and explicit new-run utilities |
| `configs/` | Recorded model settings and evaluation price snapshots |
| `docs/` | Evaluation protocol and rerunning instructions |
| `results/` | Generated analysis and figures; not tracked |

The [release scope](docs/release_scope.md) describes retained fields and the
limits of offline reproduction. `RELEASE_MANIFEST.json` lists the SHA-256 hashes
of released files.

Contract text and annotations originate from the
[ContractNLI dataset](https://stanfordnlp.github.io/contract-nli/).
The upstream dataset's terms apply to its contents. This repository does not
grant additional rights to third-party data or models.
