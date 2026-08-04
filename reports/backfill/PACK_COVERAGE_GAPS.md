# Pack coverage backfill plan

Registered packs: 23

## Gap summary

| Model | Have | Missing | Auth | Action |
|-------|-----:|---------|------|--------|
| `Beta_pangu_505b` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `Beta_pangu_92b` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `claude-fable-5` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `claude-opus-4-8` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `claude-sonnet-5` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `deepseek-v4-pro` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `gemini-3.1-pro-preview-thinking` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `glm-5.1` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `glm-5.2` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `gpt-5.4-mini` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `gpt-5.5` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `gpt-5.6-luna` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `gpt-5.6-sol` | 23/23 | — | OK* | already complete |
| `gpt-5.6-terra` | 22/23 | `recency_bias_mini` | OK | enqueue k=6 |
| `grok-build` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `qwen3.5-397b-a17b` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `qwen3.6-plus` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |
| `qwen3.7-max` | 22/23 | `recency_bias_mini` | FAIL | skip (auth/connect) |

## Auth probe FAIL (not enqueued)
- `grok-build`
- `qwen3.6-plus`
- `qwen3.5-397b-a17b`
- `qwen3.7-max`
- `deepseek-v4-pro`
- `glm-5.2`
- `gemini-3.1-pro-preview-thinking`
- `glm-5.1`
- `Beta_pangu_505b`
- `Beta_pangu_92b`


## Update 2026-07-31 — China proxy key refreshed

New key applied to `models.yaml` endpoints on `http://1.95.77.23:3000/v1`.

Auth OK and **enqueued** for `recency_bias_mini` k=6:
- deepseek-v4-pro, glm-5.1, glm-5.2, qwen3.5-397b-a17b, qwen3.6-plus, qwen3.7-max, gemini-3.1-pro-preview-thinking

Still blocked:
- glm-5.2-zp (no channel)
- grok-build (JWT on cli-chat-proxy, different credential)
- Beta_pangu_92b / 505b (naarden endpoint connection errors; key not changed to China sk)
