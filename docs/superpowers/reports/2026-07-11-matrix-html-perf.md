# Matrix HTML performance audit (2026-07-11)

Tool: agent-browser (Chrome, `--no-sandbox`) against `http://127.0.0.1:8765/reports/dsm-ae-matrix.html`

## Before

| Metric | Value |
|--------|-------|
| HTML size | 1.97 MB |
| Mermaid blocks | 300 (`pre.mermaid`) |
| SVGs after load | **300** (all rendered despite collapsed `<details>`) |
| `loadEventEnd` | **~13.9 s** |
| FCP | ~164 ms |
| Root cause | `mermaid.initialize({ startOnLoad: true })` walked every diagram on first paint; per-model flowcharts multiplied graphs × models |

## After

| Metric | Value |
|--------|-------|
| HTML size | 1.18 MB |
| Lazy Mermaid sources | 20–21 (one reference tree per syndrome) |
| SVGs after load | **0** |
| `loadEventEnd` | **~160 ms** |
| FCP | **~80–144 ms** |
| Open one syndrome → first SVG | **~56 ms** after mermaid.js cached (~126 ms CDN on cold cache) |
| Queue UI `/` | **~19 ms** loadEventEnd |

All measured pages paint/load **under 1 s**.

## Changes (`scripts/json_to_html_report.py`)

1. **Deferred Mermaid** — source in `<script type="text/plain" class="mermaid-src">`, not `pre.mermaid`.
2. **No CDN until expand** — mermaid.js injected on first open of a syndrome.
3. **`startOnLoad: false`** — never auto-render hundreds of graphs.
4. **Per-model pathways = HTML step logs only** (no Mermaid) — keeps evidence without SVG explosion.
5. Hash navigation still opens the target `<details>` and renders only that diagram.

## Regenerating

```bash
PYTHONPATH=src python3 scripts/json_to_html_report.py reports -o reports/dsm-ae-matrix.html --include-mock
```
