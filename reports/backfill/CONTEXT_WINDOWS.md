# Context window backfill

Source notes for `context_window` values written into `models.yaml` (top-level integer tokens per model entry).

**Bloat / Axis-V fill uses `context_window` as the operational denominator** (what the
request path actually enforces), not the marketing card when those differ.

Updated **2026-07-16** after [CLIProxyAPI#4195](https://github.com/router-for-me/CLIProxyAPI/issues/4195)
and OpenAI Codex `models.json` (see `context_window` vs `context_window_api`).

| model_name | context_window (ops) | context_window_api | status | source |
|---|---:|---:|---|---|
| gpt-5.5 | **272,000** | 1,050,000 | codex_catalog | Codex catalog `context_window`/`max_context_window` = 272000. API card is 1.05M ([OpenAI](https://developers.openai.com/api/docs/models/gpt-5.5)). This deployment routes via CLIProxy/Codex OAuth — **ops = catalog**. Effective UI often ~258k (×0.95). |
| gpt-5.6-terra | **372,000** | 1,050,000 | codex_catalog | Codex `models.json` + CLIProxy forward: 372000. API family card ~1.05M. Effective ~353k (×0.95). |
| gpt-5.6-sol | **372,000** | 1,050,000 | codex_catalog | Same as Terra/Luna. |
| gpt-5.6-luna | **372,000** | 1,050,000 | codex_catalog | Same as Sol/Terra. |
| Beta_pangu_92b | 512,000 | — | user_forced | Forced by operator (512k). |
| Beta_pangu_505b | 512,000 | — | user_forced | Forced by operator (512k). |
| glm-5.1 | 200,000 | — | public_spec | Z.AI docs GLM-5.1: 200K. |
| glm-5.2 | 1,000,000 | — | public_spec | Z.AI docs GLM-5.2: 1M. |
| deepseek-v4-pro | 1,000,000 | — | public_spec | DeepSeek V4-Pro: 1M. |
| qwen3.6-plus | 1,000,000 | — | public_spec | Qwen3.6-Plus: 1M default. |
| qwen3.5-397b-a17b | 262,144 | — | public_spec | Native 262,144 (YaRN extendable). |
| qwen3.7-max | 1,000,000 | — | public_spec | Listings: 1M. |
| grok-build | 512,000 | — | live_api | CLI chat proxy `/v1/models` `context_window:512000`. |

## Why GPT is not 1.05M here

| Layer | Window |
|-------|--------|
| OpenAI **API** model card | ~1,050,000 |
| OpenAI **Codex catalog** (official) | 272k (5.5) / **372k** (5.6 family) |
| CLIProxyAPI metadata | **Forwards Codex catalog** (not a proxy invention) |
| DSM-AE bloat fill (`context_window`) | **Operational path = Codex catalog** |

Filling 50% of 1.05M (~525k tokens) on this path overshoots the real ~272–372k ceiling and produces false overflow failures (observed on `tool_integrity_tier2` under bloat50 v1).

Upstream Codex catalog: `openai/codex` → `codex-rs/models-manager/models.json`.

## Notes

- `context_window` = **operational fill denominator** for bloat experiments and similar.
- Optional `context_window_api` records the API marketing number for documentation only (not read by `resolve_window_tokens` today).
- China-proxy `/v1/models` and Tailscale OpenAI-compat `/v1/models` often omit window fields — rely on this table + Codex catalog for GPT.
- Re-probe live accept/reject at 200k/300k/360k/400k if the proxy backend changes.

## models.yaml shape

```yaml
- model_name: gpt-5.6-sol
  context_window: 372000        # operational (Codex/CLIProxy)
  context_window_api: 1050000   # API card (docs only)
  litellm_params:
    model: gpt-5.6-sol
    # ...
```
