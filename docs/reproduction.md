# Reproduction and repository guide

## Reproduce the recorded results

Use **Python 3.10 or later**. From the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python -m analysis.reproduce --check
python -m analysis.figures
python -m unittest discover -s tests
```

After dependencies are installed, analysis and plotting run **offline, with no
model calls**. The analysis reads `data/predictions.jsonl`, checks the frozen
reference in `data/expected_metrics.json`, and writes `results/metrics.json`,
`results/baseline.csv`, and `results/anchor.csv`. The `--check` command also
independently recomputes request costs from sanitized usage, elapsed time, and
recorded price snapshots.

Plotting writes PDF, SVG, and PNG figures plus captions to `results/figures/`:

- **`cost_accuracy`** — baseline cost versus accuracy; descriptive 95% intervals
  remain in the metric data.
- **`correctness_response_time`** — all-twelve-correct anchor counts and median
  baseline response times.

These are portable views of the core results. This release does not claim to
recreate every appendix table, development diagnostic, or the paper's exact
figure layout. See [release scope](release_scope.md) for coverage.

## Evaluation scope

| Panel | Design | Requests per model |
| :--- | :--- | ---: |
| Official test baseline | 123 contracts × 17 judgments, jointly requested | 123 |
| Controlled test anchors | 30 contracts × 1 fixed anchor × 4 conditions × 3 repeats | 360 |

The baseline contains **2,091 intended judgments per model**. Controlled
conditions vary visible hypotheses, requested outputs, and requested output
order while preserving the target and contract. Evidence-span extraction is
outside this evaluation.

All **4,830 attempts and 13 invalid requests** remain in the released records.
Invalid requests count as incorrect and remain in cost and response-time
summaries. Requests are not repaired or replaced.

Costs combine reported API charges, token-price estimates, and local GPU
rental-equivalent estimates at **$2.00 per GPU-hour**. Response time is measured
client elapsed time, including network and service overhead. These measures do
not isolate model computation. Model settings and provider interfaces differ;
Sonnet, Terra, and Haiku were added after inspection of earlier results. See the
[full protocol](protocol.md) for inference settings, uncertainty, and limits.

## Run a new evaluation

[Rerunning instructions](rerunning.md) cover dataset preparation, adapters,
explicit inference settings, and endpoint configuration. The runner first
produces an offline request plan; sending requests requires `--execute`. Keep
new outputs separate from the frozen records.

```sh
python -m benchmark.data --output-dir data
python -m benchmark.run --panel test123 --data-dir data \
  --adapter openai --model YOUR_MODEL_ID --model-key new-model \
  --output-dir runs/new-model
```

Preparing data downloads the upstream archive unless an existing archive is
provided. A new evaluation requires an available model endpoint and can incur
charges. The package configures neither model hosting nor credentials.
Recomputing recorded results is deterministic; new hosted-model responses may
differ because models, providers, and serving configurations can change.

## Repository guide

| Path | Purpose |
| :--- | :--- |
| [`data/`](../data/) | Sanitized frozen records and reference metrics |
| [`analysis/`](../analysis/) | Offline scoring, verification, and plotting |
| [`benchmark/`](../benchmark/) | Dataset preparation and explicit new-run utilities |
| [`configs/`](../configs/) | Recorded model settings and evaluation price snapshots |
| [`docs/`](./) | Protocol, release scope, rerunning, and website maintenance |
| `results/` | Generated analysis and figures; not tracked |

[Release scope](release_scope.md) describes retained fields and reproduction
limits. [`RELEASE_MANIFEST.json`](../RELEASE_MANIFEST.json) lists released-file
SHA-256 hashes. The project website is maintained separately on `gh-pages`; see
[website maintenance](project_website.md) for publication and access details.

Contract text and annotations originate from the
[ContractNLI dataset](https://stanfordnlp.github.io/contract-nli/).
The upstream dataset's terms apply to its contents. This repository does not
grant additional rights to third-party data or models.

## Figure assets

The README displays the paper’s aggregate cost–accuracy comparison as an image. Model marks identify the evaluated systems. The accompanying LobeHub icon license is retained in [assets/LICENSE.lobe-icons](../assets/LICENSE.lobe-icons).
