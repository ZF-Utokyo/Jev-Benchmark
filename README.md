# Same score. Different decisions.

A static project page for the current contract-inference evaluation. The page uses aggregate metrics from the frozen benchmark release and makes no model calls.

Live site: https://zf-utokyo.github.io/Jev-Benchmark/

## Preview

Run `python3 -m http.server 8000` from this directory and open `http://127.0.0.1:8000/`. No build step, external fonts, analytics, or CDN dependencies are required.

The page is designed for branch-based GitHub Pages at the branch root; `.nojekyll` is included. Repository visibility and account plan determine whether GitHub Pages can serve it.

## Contents

- `index.html`: project narrative, protocol, static results table, resources
- `static/css/index.css`: responsive design
- `static/js/data.js`: sanitized aggregate model metrics
- `static/js/index.js`: plot controls, point details, navigation, and copy button
- `static/images/favicon.svg`: original equal-count / changed-decision site mark

Adapted from the user-supplied Academic Project Website Template. Its static directory layout, project-page sections, responsive navigation, and copy-button pattern were retained; placeholder content and CDN dependencies were replaced. The supplied template did not include an upstream credit URL.

## Smoke checks

Check the page at 360px and 1440px. Toggle cost/time, filter model families, select plotted points by keyboard, inspect the horizontally scrollable table, open/close mobile navigation, and copy reproduction commands. Figures and tables must remain readable without external requests; the static model table is available even when JavaScript is disabled.

## Model icons

The model table and selected-model details use the supplied vector marks for TypeSafe AI (Jev), Gemini, OpenAI, Claude, and Qwen. The TypeSafe AI mark identifies Jev’s developer. LobeHub icon assets retain their accompanying MIT license in `static/images/models/LICENSE.lobe-icons`. Brand marks identify the evaluated models and do not imply endorsement.
