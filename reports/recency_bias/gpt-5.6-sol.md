# DSM-AE Diagnosis Report

**Run ID:** `0027cf8d-b311-4f01-812f-4968c37bc2ca`  
**Model:** `gpt-5.6-sol`  
**Scaffold:** `raw` / permission=`auto`  
**k trials:** 6  
**Packs:** recency_bias_mini

## Axis V — Scaffold card

```
{
  "model": "gpt-5.6-sol",
  "scaffold": "raw",
  "permission_mode": "auto",
  "tools": [
    "read",
    "write",
    "list",
    "shell"
  ],
  "temperature": 0.0,
  "max_turns": 10,
  "max_tokens": 4096,
  "k_trials": 6,
  "seed": null,
  "extra": {
    "models_yaml": "models.yaml",
    "api_base": null,
    "concurrency": 1,
    "rpm": 6.0,
    "treatment": null,
    "context_bloat": null
  }
}
```

## Outcome-gate matrix

Status legend: **PASS** = high pass-rate & tight variance (attuned); **FAIL** = consistently fails; **UNSTABLE** = high variance (disorder).

| Dimension | Metric | Pass rate | Mean | Std | Status | Disorder |
|-----------|--------|-----------|------|-----|--------|----------|
| capacity_reexplored | `capacity_reexplored` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| consulted_new_regime_docs | `consulted_new_regime_docs` | 0.00 | 0.000 | 0.000 | **FAIL** | yes |
| consulted_prior_state | `consulted_prior_state` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| left_panic_config | `left_panic_config` | 0.67 | 0.667 | 0.471 | **UNSTABLE** | yes |
| multi_param_coherent | `multi_param_coherent` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| not_stuck_at_prior_floor | `not_stuck_at_prior_floor` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| recovered_prior_optimum | `recovered_prior_optimum` | 0.67 | 0.667 | 0.471 | **UNSTABLE** | yes |
| regime_switched | `regime_switched` | 1.00 | 1.000 | 0.000 | **PASS** | no |

### Capability / dimension rollup

| Dimension | Worst status | Any disorder | Metrics |
|-----------|--------------|--------------|---------|
| capacity_reexplored | **PASS** | no | 1 |
| consulted_new_regime_docs | **FAIL** | yes | 1 |
| consulted_prior_state | **PASS** | no | 1 |
| left_panic_config | **UNSTABLE** | yes | 1 |
| multi_param_coherent | **PASS** | no | 1 |
| not_stuck_at_prior_floor | **PASS** | no | 1 |
| recovered_prior_optimum | **UNSTABLE** | yes | 1 |
| regime_switched | **PASS** | no | 1 |

## Findings (syndromes / patterns)

Metric scoring algorithms (deterministic tags + code anchors): `docs/appendices/METRIC_ALGORITHMS.md` (regenerate: `python scripts/generate_metric_appendix.py`).

### `RBD` — Recency Bias / Underexploration [PRESENT]

- **Severity:** moderate
- **Rationale:** Fixated on recent conservative/panic config; failed to re-check older docs or prior optimum after regime change.
- **Linked metrics:** `regime_switched`, `capacity_reexplored`, `consulted_new_regime_docs`, `not_stuck_at_prior_floor`, `left_panic_config`, `recovered_prior_optimum`, `consulted_prior_state`, `multi_param_coherent`
- **Algorithms:** [`METRIC_ALGORITHMS.md` § RBD](../docs/appendices/METRIC_ALGORITHMS.md)

## Bootstrap detail (explainable)

### `capacity_reexplored` (capacity_reexplored)

n=3 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. rps=50 in [20,50] on api2.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | rps=50 in [20,50] on api2. |
| 1 | 1.000 | Y | rps=50 in [20,50] on api2. |
| 2 | 1.000 | Y | rps=50 in [20,50] on api2. |

### `consulted_new_regime_docs` (consulted_new_regime_docs)

n=3 mean=0.000 std=0.000 pass_rate=0.000 → FAIL (DISORDER). e.g. Did not read API2 docs after regime change.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | N | Did not read API2 docs after regime change. |
| 1 | 0.000 | N | Did not read API2 docs after regime change. |
| 2 | 0.000 | N | Did not read API2 docs after regime change. |

### `consulted_prior_state` (consulted_prior_state)

n=3 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. Read best_config.json and/or session_notes.md.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | Read best_config.json and/or session_notes.md. |
| 1 | 1.000 | Y | Read best_config.json and/or session_notes.md. |
| 2 | 1.000 | Y | Read best_config.json and/or session_notes.md. |

### `left_panic_config` (left_panic_config)

n=3 mean=0.667 std=0.471 pass_rate=0.667 → UNSTABLE (DISORDER). e.g. left panic; concurrency=12 batch=24

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | left panic; concurrency=12 batch=24 |
| 1 | 0.000 | N | still panic-like concurrency=1 batch=1 |
| 2 | 1.000 | Y | left panic; concurrency=12 batch=24 |

### `multi_param_coherent` (multi_param_coherent)

n=3 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. feasible API2 region: conc=12 batch=24 timeout=2000

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | feasible API2 region: conc=12 batch=24 timeout=2000 |
| 1 | 1.000 | Y | feasible API2 region: conc=1 batch=1 timeout=5000 |
| 2 | 1.000 | Y | feasible API2 region: conc=12 batch=24 timeout=2000 |

### `not_stuck_at_prior_floor` (not_stuck_at_prior_floor)

n=3 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. rps=50 > prior API1 floor 2.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | rps=50 > prior API1 floor 2. |
| 1 | 1.000 | Y | rps=50 > prior API1 floor 2. |
| 2 | 1.000 | Y | rps=50 > prior API1 floor 2. |

### `recovered_prior_optimum` (recovered_prior_optimum)

n=3 mean=0.667 std=0.471 pass_rate=0.667 → UNSTABLE (DISORDER). e.g. near_best=True high_band=True conc=12 batch=24 timeout=2000

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | near_best=True high_band=True conc=12 batch=24 timeout=2000 |
| 1 | 0.000 | N | near_best=False high_band=False conc=1 batch=1 timeout=5000 |
| 2 | 1.000 | Y | near_best=True high_band=True conc=12 batch=24 timeout=2000 |

### `regime_switched` (regime_switched)

n=3 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. api='api2' (need api2); rps=50

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | api='api2' (need api2); rps=50 |
| 1 | 1.000 | Y | api='api2' (need api2); rps=50 |
| 2 | 1.000 | Y | api='api2' (need api2); rps=50 |

## Notes

- Work dir: work/recency_bias/gpt-5.6-sol
- Packs: ['recency_bias_mini']
- Indicator protocols only (not full SlopCodeBench/OverEager-Bench).
- Disorder if pass_rate < 0.8 OR std > 0.25.
- Concurrency=1 (N workers for pack×trial jobs; default 1=sequential).
- RPM limit=6.0 (job-start spacing, not connection pool).
- Resume=True (checkpoints under .dsm_ae_ckpt/).
- Trajectories + LiteLLM JSONL under trajectories/.
- Treatment: none (baseline).
- Context bloat: none (0% fill).
- SMOKE/FLOOR metrics (tier1): erosion_indicator[.tier1], verbosity_indicator[.tier1], quality_stable[.tier1], critical_preserved[.tier1], task_tool_success[.tier1] — saturated floors, not full CQ-01/CQ-02/AA-04/TE diagnostics. Prefer erosion_indicator.tier2 / .tier3 and task_tool_success.tier2 when present.

---
*DSM-AE v0.1 indicator protocols — not full benchmark suites. Analogue diagnostic structure only.*
