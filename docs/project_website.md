# Project website

The benchmark repository and its website serve different purposes:

- **`main`** contains the Python package, frozen records, protocol, and README.
- **`gh-pages`** contains the static project website and its presentation assets.
  It does not replace the benchmark package or create new evaluation results.

The project site is published at
[https://zf-utokyo.github.io/Jev-Benchmark/](https://zf-utokyo.github.io/Jev-Benchmark/).
GitHub Pages uses the root directory of `gh-pages`, with HTTPS enabled.
The benchmark repository is public, and the README links to this site.

## Publication and access

GitHub Pages must be configured for the `gh-pages` branch and its root directory.
Publishing from a private repository requires an eligible GitHub plan. If
GitHub rejects that configuration, the website source can remain ready on its
branch without a live Pages deployment; repository visibility must not be
changed merely to bypass the restriction.

The website and benchmark code are publicly accessible. The separate manuscript
repository has its own access settings. The manuscript link points to LaTeX source for
*Cost–Accuracy Trade-offs in Contract Inference: Evaluating Jev and Language
Models*; it is not a public PDF or publication record. Do not describe private
links as public downloads.

## Updating the website

1. Edit the static website in a separate checkout of `gh-pages` so the Python
   package and frozen records on `main` remain easy to review.
2. Preserve the exact paper title and the formal-test scope: ten models,
   123 baseline contracts, 30 test anchors, 4,830 attempts, and 13 invalid attempts.
3. Verify every displayed value against `data/expected_metrics.json` on `main`.
   The README graphic is a static view of these same metrics; update it if the
   displayed reference results change.
4. Preview the site on desktop and mobile. Check relative asset paths, accessible
   labels, table overflow, keyboard controls, and code-copy behavior.
5. Inspect the proposed files before publishing. Website files must contain no
   credentials, connection settings, personal filesystem paths, raw operational
   records, or unapproved manuscript artifacts.
6. Commit using the maintainer's configured Git identity and push the website
   branch. Check GitHub Pages deployment status and the rendered site before
   replacing the README's source-branch link with the live project URL.

For changes on `main`, rerun the documented offline checks and refresh the
release manifest after all tracked content has settled. Website updates alone
do not authorize fresh inference or changes to frozen benchmark records.

## Scientific presentation

The website should distinguish baseline accuracy from correctness throughout
all four conditions and three repeats. Stable wrong answers contribute to
agreement but do not count as all-twelve-correct answers. Describe cost and
response-time comparisons under the recorded accounting and deployment
conditions, and retain the documented uncertainty and reproduction limits.
