# Bloated context — 50% stage (v2 · Codex operational windows)

**Condition:** `bloat50` (level=0.5)  
**Version:** v2 (2026-07-16) — **invalidates v1** which used API marketing 1.05M for GPT.

## Windows used for fill %

| Model | `context_window` (ops) | 50% target (pre-reserve) | Notes |
|-------|----------------------:|-------------------------:|-------|
| gpt-5.5 | 272,000 | ~136k | Codex catalog (CLIProxy path) |
| gpt-5.6-sol | 372,000 | ~186k | Codex catalog |
| qwen3.5-397b-a17b | 262,144 | ~131k | Public native window |
| qwen3.6-plus | 1,000,000 | ~500k | Public 1M |

GPT **API** cards still advertise 1.05M (`context_window_api` in models.yaml) but this
deployment routes through Codex/CLIProxy — fill uses operational catalog values.
See `reports/backfill/CONTEXT_WINDOWS.md` and CLIProxyAPI#4195.

**Packs:** all registered · **k:** 10 · **concurrency:** 8 per model job  
**Token method:** char4 (UTF-8 bytes/4) · **overflow → trial fail**

## Artifacts

- `work/{model}/` — trajectories + checkpoints  
- `{model}.json` / `.md` — diagnosis reports  
- `comparison.html` — Comparison tab (baseline vs 50%)

Rebuild comparison:

```bash
python3 scripts/build_bloat_comparison.py --models gpt-5.5,gpt-5.6-sol,qwen3.5-397b-a17b,qwen3.6-plus
```

Enqueue:

```bash
python3 scripts/enqueue_bloat50.py --concurrency 8 --label-suffix -v2-codex-window
```
