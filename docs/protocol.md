# Evaluation protocol

## Task and panels

The task is contract–hypothesis classification using the original ContractNLI
annotations: `entailment`, `contradiction`, or `not_mentioned`. Evidence-span
extraction is outside this evaluation. Inputs retain the full contract and
original hypotheses; gold labels and evidence annotations are not model inputs.

The official test baseline has 123 contracts, 17 hypotheses per contract, and
2,091 judgments: 968 entailments, 220 contradictions, and 903 not-mentioned
labels. One request jointly predicts all 17 labels for each contract. The
stability panel is a subset of 30 test contracts with one fixed target, or
anchor, per contract. Selection uses seed 20260922 and document-specific anchor
seeds, independently of labels and predictions. The dataset-preparation code
specifies the exact selection procedure.

| Condition | Visible hypotheses | Requested outputs |
| --- | --- | --- |
| A | Anchor only | Anchor only |
| B | All 17, in fixed catalog order | Anchor only |
| C | All 17, in fixed catalog order | All 17, anchor first |
| D | All 17, in fixed catalog order | All 17, anchor last |

Each condition is repeated three times. This gives 360 requests per model and
90 primary anchor responses per condition, but only 30 independent contract
targets. The additional labels returned by C and D do not create extra primary
targets. The baseline and anchor analyses share contracts and should not be
treated as independent samples.

Together, these panels contain 4,830 recorded attempts across ten models.

Requests are sequential within a model; different models may run concurrently.
Condition and repeat order are shuffled within each contract using the fixed
schedule. Failed attempts are retained without automatic retries, repair, or
replacement. The original test collections used the same client machine.

## Validity and quality metrics

A valid response returns exactly the requested IDs and one allowed label for
each. Invalid responses, including exhausted generation allowances without final
labels, contribute no correct labels. Every intended judgment stays in the
accuracy denominator. Macro-F1 is the unweighted mean of the three class F1
scores, and class recalls use the corresponding gold-label denominators.

The four mutually exclusive anchor outcomes are:

- **All 12 correct:** all four conditions and all three repeats return the
  correct anchor label.
- **Stable wrong:** all twelve labels are valid, identical, and incorrect.
- **Changed valid:** all twelve labels are valid and at least two differ.
- **Invalid:** at least one response is invalid; this category takes precedence.

The counts sum to 30. Mean anchor correctness separately averages all 360
anchor responses, treating invalid responses as incorrect. All-twelve
correctness and this mean use identical targets. Baseline accuracy uses a
broader target set, so differences in their model rankings can reflect both
sample composition and sensitivity to request conditions.

Condition transitions pair the same contract, anchor, and repeat. Label-change
rates use only pairs valid in both conditions, with valid-pair coverage reported
separately. A change can be correct-to-wrong, wrong-to-correct, or a switch
between incorrect labels. Accuracy differences can conceal corrections and
regressions that cancel. Unchanged-request disagreement describes variability
within a condition; subtracting it from a condition difference does not identify
a causal effect.

## Uncertainty

Descriptive 95% percentile intervals use 5,000 whole-contract bootstrap samples
with seed 20260922. Paired comparisons preserve each contract's observations
across models. Anchor resampling retains all conditions and repeats within each
contract. Repeats do not increase the number of independent sampling units.
Intervals are not adjusted for multiple comparisons, and zero observed changes
can produce a degenerate interval. Point rankings and frontier membership do
not establish statistically reliable differences.

## Evaluated configurations

The formal comparison contains Jev 1.13.0; Qwen3.5-4B and Qwen3.5-9B; Gemini 3.5
Flash-Lite and Gemini 3.1 Pro Preview; GPT-5.6 Luna and Terra; GPT-6 Astra;
Claude Sonnet 5; and Claude Haiku 4.5. Public display names identify the recorded
configurations; the rerun utilities require an explicit endpoint model ID.
Recorded request model IDs and generation settings are in `configs/models.json`.

Jev represents the contract as shared state and each hypothesis as a native
Choice question. Generative models receive aligned classification instructions
and return a JSON label map. The baseline and controlled-catalog prompts differ,
with each prompt fixed within its comparisons. Jev's C/D intervention changes
question-key order and need not correspond to an autoregressive output-position
intervention. Requested order also need not match internal reasoning order.

Flash-Lite uses minimal thinking, Gemini Pro low thinking, Luna no reasoning,
and Astra high reasoning. Terra uses medium reasoning with a 16,384-token output
allowance. Sonnet uses adaptive thinking with medium effort and a 16,384-token
allowance; Haiku disables thinking with an 8,192-token allowance. Both Qwen test
configurations use BF16, enabled thinking, temperature 1, top-p 0.95, one GPU
per model, and a shared allowance of 32,768 tokens for reasoning and final
labels. These settings do not equalize computation or actual reasoning length.

The task, inputs, target selection, and scoring rules were fixed before test
inference. Terra, Sonnet, and Haiku were added after inspection of earlier
results, with their settings fixed before their own test collection. The
ten-model selection is therefore not wholly prospective. Provider routes and
interfaces differ between configurations and remain part of the measurements.

## Cost accounting

Cost covers the same attempted requests used for quality, including failures.
Luna and Astra use provider-reported API charges. Other API configurations use
recorded token usage and the input, output, and cache prices applied in the
evaluation. The published comparison therefore mixes billing observations and
estimates. The clean records retain each request's numerical cost and basis;
offline analysis aggregates these recorded values rather than querying current
prices. Missing costs remain unknown, with coverage and the known subtotal
reported separately.

Jev's snapshot price is $0.042 per million input tokens, with no output-token
charge in this accounting. Price snapshots document the evaluated rates and do
not claim to be current prices.

For each local model, baseline GPU rental-equivalent cost per contract is

```text
(2.00 USD per GPU-hour) × sum(request seconds) / (123 × 3600)
```

Each configuration uses one GPU. The $2.00 rate values observed request time;
it is not a measured bill or an estimate of cloud throughput. Loading, idle
allocation, storage, transfer, and taxes are excluded. Hardware and serving
differences remain. A cost–accuracy frontier describes nondominated observed
configurations under these assumptions; it is neither a significance test nor
a claim that intermediate configurations were evaluated.

## Response time

Response time is the recorded client elapsed time, including request
preparation, connection establishment, network transfer, service processing,
and response validation. All attempts, including invalid responses, enter the
median and P95. P95 uses linear interpolation between ordered observations.
There is one in-flight request per model and no retries. Caching and provider
infrastructure are part of the evaluated deployments.

These observations do not isolate model computation, queueing, or time to first
token. A small change in elapsed time when more outputs are requested does not
by itself establish internal parallelism. Baseline and condition-specific
workloads must be named when comparing times.

## Release coverage

The supplied frozen prediction records and offline analysis cover the formal
test baseline and test-anchor panel for the ten configurations. Portable plots
show baseline cost and accuracy, all-twelve-correct counts, and baseline median
response time. Development sampling utilities support preparing the original
development panels, but this release does not claim complete reproduction of
every development experiment or appendix figure. New inference is separate
from offline reproduction and can produce different responses.
