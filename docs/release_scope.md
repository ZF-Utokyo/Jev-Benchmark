# Release scope

This initial release contains the ten-model formal test comparison: 1,230
baseline attempts and 3,600 anchor attempts. All 13 invalid attempts remain in
the released records. Twelve ended at the Qwen output limit; one Gemini Pro
failure is retained as an unspecified API failure because the saved evidence
does not identify a narrower cause.

## Frozen records

`data/predictions.jsonl` contains an allowlisted export, not the original API
logs. Each row retains a public dataset document ID, model ID, target and
condition, repeat index, gold and predicted labels, validity, a fixed failure
category, completion reason, normalized numeric usage, cost and client elapsed
time. Baseline rows contain all 17 target judgments. Anchor rows retain only
the preselected primary target, even when the original request returned all
17 labels. No answer is repaired or replaced during export.

Failed predictions are empty. Missing usage and unknown cost remain null.
Cached-input counts use each provider's documented accounting convention.
Gemini completion counts include thinking tokens. Cost calculation is checked
against the frozen per-attempt values using `configs/pricing.json`.

`data/expected_metrics.json` is a frozen reference projection from the completed
study report. `analysis.reproduce --check` independently recomputes its metrics
from the released predictions, including the whole-contract bootstrap
intervals and paired comparisons. It does not copy scores from the reference.

`data/splits.json` records the official test IDs and anchor selection.
`data/provenance.json` includes hashes of the export and original source files;
source file paths and machine identifiers are omitted. The original files are
not distributed, so their hashes are provenance identifiers rather than a way
to inspect the unavailable contents.

## What can be reproduced

The release supports the core formal-test classification metrics, failure
counts, anchor outcome partition, request-condition transitions, within-condition
repeat disagreement, listed-rate or reported-charge costs, GPU rental
equivalents, and recorded response-time summaries. The plotting code provides
portable core-result views and the table exporter produces CSV summaries.

Full request payloads and responses are absent. Consequently, this release
does not independently reparse each historical raw response, inspect reasoning
text, audit every historical output-order detail, or reproduce every development
diagnostic and appendix table. Original end-to-end times are observed records;
offline analysis does not measure new latency. New hosted-model inference is a
separate experiment and need not reproduce historical labels or timings.

## Excluded material

No authentication values or saved authentication headers, personal credential
configuration, server connection details, personal paths, private account
identifiers, unfiltered exception messages, raw API bodies, operational logs,
or inherited repository history are included. New inference obtains connection
settings from the invoking process and keeps them out of recorded results.

Original contracts are downloaded from the official dataset when preparing a
new evaluation. Generated dataset panels, new run outputs and local analysis
artifacts are ignored by Git. The existing manuscript repository is separate.
