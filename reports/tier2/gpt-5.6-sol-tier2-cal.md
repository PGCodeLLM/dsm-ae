# DSM-AE Diagnosis Report

**Run ID:** `e67cb9a7-4cdc-4131-87ad-99e22e812ca8`  
**Model:** `gpt-5.6-sol`  
**Scaffold:** `raw` / permission=`auto`  
**k trials:** 2  
**Packs:** slop_indicator, erosion_tier2, erosion_tier3

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
  "k_trials": 2,
  "seed": null,
  "extra": {
    "models_yaml": "models.yaml",
    "api_base": null,
    "concurrency": 2,
    "rpm": 6.0,
    "treatment": null
  }
}
```

## Outcome-gate matrix

Status legend: **PASS** = high pass-rate & tight variance (attuned); **FAIL** = consistently fails; **UNSTABLE** = high variance (disorder).

| Dimension | Metric | Pass rate | Mean | Std | Status | Disorder |
|-----------|--------|-----------|------|-----|--------|----------|
| c1_implements | `c1_implements` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| c2_extends | `c2_extends` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| erosion_indicator | `erosion_indicator` | 1.00 | 0.000 | 0.000 | **PASS** | no |
| erosion_indicator.tier1 | `erosion_indicator.tier1` | 1.00 | 0.000 | 0.000 | **PASS** | no |
| erosion_indicator.tier2 | `erosion_indicator.tier2` | 0.00 | 0.825 | 0.205 | **FAIL** | yes |
| erosion_indicator.tier3 | `erosion_indicator.tier3` | 0.50 | 0.379 | 0.426 | **UNSTABLE** | yes |
| erosion_slope | `erosion_slope` | 0.62 | 0.056 | 0.104 | **FAIL** | yes |
| extract_discipline | `extract_discipline` | 0.00 | 0.000 | 0.000 | **FAIL** | yes |
| god_function_mass | `god_function_mass` | 0.00 | 0.943 | 0.023 | **FAIL** | yes |
| quality_stable | `quality_stable` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| quality_stable.tier1 | `quality_stable.tier1` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| quality_stable.tier3 | `quality_stable.tier3` | 0.62 | 0.625 | 0.484 | **UNSTABLE** | yes |
| tier2_features_land | `tier2_features_land` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| tier3_features_land | `tier3_features_land` | 0.88 | 0.875 | 0.331 | **UNSTABLE** | yes |
| verbosity_indicator | `verbosity_indicator` | 1.00 | 0.000 | 0.000 | **PASS** | no |
| verbosity_indicator.tier1 | `verbosity_indicator.tier1` | 1.00 | 0.000 | 0.000 | **PASS** | no |

### Capability / dimension rollup

| Dimension | Worst status | Any disorder | Metrics |
|-----------|--------------|--------------|---------|
| c1_implements | **PASS** | no | 1 |
| c2_extends | **PASS** | no | 1 |
| erosion_indicator | **PASS** | no | 1 |
| erosion_indicator.tier1 | **PASS** | no | 1 |
| erosion_indicator.tier2 | **FAIL** | yes | 1 |
| erosion_indicator.tier3 | **UNSTABLE** | yes | 1 |
| erosion_slope | **FAIL** | yes | 1 |
| extract_discipline | **FAIL** | yes | 1 |
| god_function_mass | **FAIL** | yes | 1 |
| quality_stable | **PASS** | no | 1 |
| quality_stable.tier1 | **PASS** | no | 1 |
| quality_stable.tier3 | **UNSTABLE** | yes | 1 |
| tier2_features_land | **PASS** | no | 1 |
| tier3_features_land | **UNSTABLE** | yes | 1 |
| verbosity_indicator | **PASS** | no | 1 |
| verbosity_indicator.tier1 | **PASS** | no | 1 |

## Findings (syndromes / patterns)

### `ISDS` — Iterative Slop Degradation (indicator) [PRESENT]

- **Severity:** severe
- **Rationale:** Erosion/verbosity indicators unstable or above threshold (erosion mean=0.82).
- **Linked metrics:** `erosion_indicator`, `erosion_indicator.tier1`, `erosion_indicator.tier2`, `erosion_indicator.tier3`, `verbosity_indicator`, `verbosity_indicator.tier1`, `quality_stable`, `quality_stable.tier1`, `quality_stable.tier3`, `erosion_slope`, `god_function_mass`, `extract_discipline`

## Bootstrap detail (explainable)

### `c1_implements` (c1_implements)

n=4 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. C1 implement gate (ckpt=1): True.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | C1 implement gate (ckpt=1): True. |
| 1 | 1.000 | Y | C1 implement gate (ckpt=2): n/a on c2. |
| 2 | 1.000 | Y | C1 implement gate (ckpt=1): True. |
| 3 | 1.000 | Y | C1 implement gate (ckpt=2): n/a on c2. |

### `c2_extends` (c2_extends)

n=4 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. C2 extend gate (ckpt=1): n/a on c1.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | C2 extend gate (ckpt=1): n/a on c1. |
| 1 | 1.000 | Y | C2 extend gate (ckpt=2): True. |
| 2 | 1.000 | Y | C2 extend gate (ckpt=1): n/a on c1. |
| 3 | 1.000 | Y | C2 extend gate (ckpt=2): True. |

### `erosion_indicator` (erosion_indicator)

n=4 mean=0.000 std=0.000 pass_rate=1.000 → PASS (attuned) [SMOKE/FLOOR]. e.g. Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=4, n_funcs=6, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope or BMAD-rigorous structure. See erosion_indicator.tier2 / .tier3 for deeper diagnostics.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=4, n_funcs=6, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |
| 1 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=6, n_funcs=8, loc=65. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |
| 2 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=3, n_funcs=3, loc=21. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |
| 3 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=4, n_funcs=3, loc=27. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |

### `erosion_indicator.tier1` (erosion_indicator.tier1)

n=4 mean=0.000 std=0.000 pass_rate=1.000 → PASS (attuned) [SMOKE/FLOOR]. e.g. Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=4, n_funcs=6, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope or BMAD-rigorous structure. See erosion_indicator.tier2 / .tier3 for deeper diagnostics.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=4, n_funcs=6, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |
| 1 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=6, n_funcs=8, loc=65. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |
| 2 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=3, n_funcs=3, loc=21. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |
| 3 | 0.000 | Y | Structural erosion indicator=0.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=4, n_funcs=3, loc=27. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ |

### `erosion_indicator.tier2` (erosion_indicator.tier2)

n=4 mean=0.825 std=0.205 pass_rate=0.000 → FAIL (DISORDER). e.g. Tier2 structural erosion score=1.000 (0=clean extraction, 1=god-function patch). passed=False. findings=['god_function_mass', 'patch_into_hot_function', 'extract_refusal', 'complexity_concentration']. max_cc=34 (seed=26), max_mass_share=0.975 (seed=0.969), n_funcs=2 (seed=2). BMAD-structural: god-mass / patch-into-hot / extract-refusal.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | N | Tier2 structural erosion score=1.000 (0=clean extraction, 1=god-function patch). passed=False. findings=['god_function_mass', 'patch_into_hot_function', 'extrac |
| 1 | 1.000 | N | Tier2 structural erosion score=1.000 (0=clean extraction, 1=god-function patch). passed=False. findings=['god_function_mass', 'patch_into_hot_function', 'extrac |
| 2 | 0.500 | N | Tier2 structural erosion score=0.500 (0=clean extraction, 1=god-function patch). passed=False. findings=['god_function_mass', 'complexity_concentration']. max_c |
| 3 | 0.800 | N | Tier2 structural erosion score=0.800 (0=clean extraction, 1=god-function patch). passed=False. findings=['god_function_mass', 'patch_into_hot_function', 'comple |

### `erosion_indicator.tier3` (erosion_indicator.tier3)

n=8 mean=0.379 std=0.426 pass_rate=0.500 → UNSTABLE (DISORDER). e.g. Tier3 slope-aware erosion=0.000 (abs_e=0.000, slope_e=0.0000/ckpt, slope_fail=False, abs_fail=False). n_ckpts=1, max_cc=6. Fail if slope_e>0.03 even when abs_e<0.5.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | Y | Tier3 slope-aware erosion=0.000 (abs_e=0.000, slope_e=0.0000/ckpt, slope_fail=False, abs_fail=False). n_ckpts=1, max_cc=6. Fail if slope_e>0.03 even when abs_e< |
| 1 | 0.000 | Y | Tier3 slope-aware erosion=0.000 (abs_e=0.000, slope_e=0.0000/ckpt, slope_fail=False, abs_fail=False). n_ckpts=2, max_cc=7. Fail if slope_e>0.03 even when abs_e< |
| 2 | 0.000 | Y | Tier3 slope-aware erosion=0.000 (abs_e=0.000, slope_e=0.0000/ckpt, slope_fail=False, abs_fail=False). n_ckpts=3, max_cc=7. Fail if slope_e>0.03 even when abs_e< |
| 3 | 0.000 | Y | Tier3 slope-aware erosion=0.000 (abs_e=0.000, slope_e=0.0000/ckpt, slope_fail=False, abs_fail=False). n_ckpts=4, max_cc=0. Fail if slope_e>0.03 even when abs_e< |
| 4 | 0.700 | N | Tier3 slope-aware erosion=0.700 (abs_e=0.700, slope_e=0.0000/ckpt, slope_fail=False, abs_fail=True). n_ckpts=1, max_cc=9. Fail if slope_e>0.03 even when abs_e<0 |
| 5 | 1.000 | N | Tier3 slope-aware erosion=1.000 (abs_e=1.000, slope_e=0.3000/ckpt, slope_fail=True, abs_fail=True). n_ckpts=2, max_cc=0. Fail if slope_e>0.03 even when abs_e<0. |
| 6 | 1.000 | N | Tier3 slope-aware erosion=1.000 (abs_e=1.000, slope_e=0.1500/ckpt, slope_fail=True, abs_fail=True). n_ckpts=3, max_cc=0. Fail if slope_e>0.03 even when abs_e<0. |
| 7 | 0.335 | N | Tier3 slope-aware erosion=0.335 (abs_e=0.335, slope_e=-0.1217/ckpt, slope_fail=True, abs_fail=True). n_ckpts=4, max_cc=14. Fail if slope_e>0.03 even when abs_e< |

### `erosion_slope` (erosion_slope)

n=8 mean=0.056 std=0.104 pass_rate=0.625 → FAIL (DISORDER). e.g. Erosion slope=0.0000 per checkpoint (fail if >0.03 with material rise). series=[0.0].

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | Y | Erosion slope=0.0000 per checkpoint (fail if >0.03 with material rise). series=[0.0]. |
| 1 | 0.000 | Y | Erosion slope=0.0000 per checkpoint (fail if >0.03 with material rise). series=[0.0, 0.0]. |
| 2 | 0.000 | Y | Erosion slope=0.0000 per checkpoint (fail if >0.03 with material rise). series=[0.0, 0.0, 0.0]. |
| 3 | 0.000 | Y | Erosion slope=0.0000 per checkpoint (fail if >0.03 with material rise). series=[0.0, 0.0, 0.0, 0.0]. |
| 4 | 0.000 | Y | Erosion slope=0.0000 per checkpoint (fail if >0.03 with material rise). series=[0.7]. |
| 5 | 0.300 | N | Erosion slope=0.3000 per checkpoint (fail if >0.03 with material rise). series=[0.7, 1.0]. |
| 6 | 0.150 | N | Erosion slope=0.1500 per checkpoint (fail if >0.03 with material rise). series=[0.7, 1.0, 1.0]. |
| 7 | 0.000 | N | Erosion slope=-0.1217 per checkpoint (fail if >0.03 with material rise). series=[0.7, 1.0, 1.0, 0.33483217204442006]. |

### `extract_discipline` (extract_discipline)

n=4 mean=0.000 std=0.000 pass_rate=0.000 → FAIL (DISORDER). e.g. Extract refusal / patch-into-hot: complexity stayed concentrated.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | N | Extract refusal / patch-into-hot: complexity stayed concentrated. |
| 1 | 0.000 | N | Extract refusal / patch-into-hot: complexity stayed concentrated. |
| 2 | 0.000 | N | Extract refusal / patch-into-hot: complexity stayed concentrated. |
| 3 | 0.000 | N | Extract refusal / patch-into-hot: complexity stayed concentrated. |

### `god_function_mass` (god_function_mass)

n=4 mean=0.943 std=0.023 pass_rate=0.000 → FAIL (DISORDER). e.g. God-function mass: max_mass_share=0.975, max_cc=34 (pass if share<0.55 and max_cc≤12).

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.975 | N | God-function mass: max_mass_share=0.975, max_cc=34 (pass if share<0.55 and max_cc≤12). |
| 1 | 0.956 | N | God-function mass: max_mass_share=0.956, max_cc=43 (pass if share<0.55 and max_cc≤12). |
| 2 | 0.917 | N | God-function mass: max_mass_share=0.917, max_cc=33 (pass if share<0.55 and max_cc≤12). |
| 3 | 0.925 | N | God-function mass: max_mass_share=0.925, max_cc=35 (pass if share<0.55 and max_cc≤12). |

### `quality_stable` (quality_stable)

n=4 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned) [SMOKE/FLOOR]. e.g. Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope or BMAD-rigorous structure. See erosion_indicator.tier2 / .tier3 for deeper diagnostics.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |
| 1 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |
| 2 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |
| 3 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |

### `quality_stable.tier1` (quality_stable.tier1)

n=4 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned) [SMOKE/FLOOR]. e.g. Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope or BMAD-rigorous structure. See erosion_indicator.tier2 / .tier3 for deeper diagnostics.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |
| 1 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |
| 2 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |
| 3 | 1.000 | Y | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint (absolute gates only — not ΔC1→C2). SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slo |

### `quality_stable.tier3` (quality_stable.tier3)

n=8 mean=0.625 std=0.484 pass_rate=0.625 → UNSTABLE (DISORDER). e.g. Quality stable across multi-ckpt trajectory (no material erosion rise).

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | Quality stable across multi-ckpt trajectory (no material erosion rise). |
| 1 | 1.000 | Y | Quality stable across multi-ckpt trajectory (no material erosion rise). |
| 2 | 1.000 | Y | Quality stable across multi-ckpt trajectory (no material erosion rise). |
| 3 | 1.000 | Y | Quality stable across multi-ckpt trajectory (no material erosion rise). |
| 4 | 1.000 | Y | Quality stable across multi-ckpt trajectory (no material erosion rise). |
| 5 | 0.000 | N | Quality unstable: erosion rising across checkpoints. |
| 6 | 0.000 | N | Quality unstable: erosion rising across checkpoints. |
| 7 | 0.000 | N | Quality unstable: erosion rising across checkpoints. |

### `tier2_features_land` (tier2_features_land)

n=4 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. Tier2 feature gates ckpt=1: {'exclude': True, 'max_bytes': True}.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | Tier2 feature gates ckpt=1: {'exclude': True, 'max_bytes': True}. |
| 1 | 1.000 | Y | Tier2 feature gates ckpt=2: {'exclude': True, 'max_bytes': True, 'context': True, 'line_mode': True}. |
| 2 | 1.000 | Y | Tier2 feature gates ckpt=1: {'exclude': True, 'max_bytes': True}. |
| 3 | 1.000 | Y | Tier2 feature gates ckpt=2: {'exclude': True, 'max_bytes': True, 'context': True, 'line_mode': True}. |

### `tier3_features_land` (tier3_features_land)

n=8 mean=0.875 std=0.331 pass_rate=0.875 → UNSTABLE (DISORDER). e.g. Tier3 feature gate ckpt=1: ok=True.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | Tier3 feature gate ckpt=1: ok=True. |
| 1 | 1.000 | Y | Tier3 feature gate ckpt=2: ok=True. |
| 2 | 1.000 | Y | Tier3 feature gate ckpt=3: ok=True. |
| 3 | 0.000 | N | Tier3 feature gate ckpt=4: ok=False. |
| 4 | 1.000 | Y | Tier3 feature gate ckpt=1: ok=True. |
| 5 | 1.000 | Y | Tier3 feature gate ckpt=2: ok=True. |
| 6 | 1.000 | Y | Tier3 feature gate ckpt=3: ok=True. |
| 7 | 1.000 | Y | Tier3 feature gate ckpt=4: ok=True. |

### `verbosity_indicator` (verbosity_indicator)

n=4 mean=0.000 std=0.000 pass_rate=1.000 → PASS (attuned) [SMOKE/FLOOR]. e.g. Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope or BMAD-rigorous structure. See erosion_indicator.tier2 / .tier3 for deeper diagnostics.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |
| 1 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=65. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |
| 2 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=21. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |
| 3 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=27. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |

### `verbosity_indicator.tier1` (verbosity_indicator.tier1)

n=4 mean=0.000 std=0.000 pass_rate=1.000 → PASS (attuned) [SMOKE/FLOOR]. e.g. Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope or BMAD-rigorous structure. See erosion_indicator.tier2 / .tier3 for deeper diagnostics.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=42. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |
| 1 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=65. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |
| 2 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=21. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |
| 3 | 0.000 | Y | Verbosity indicator=0.000 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=0, loc=27. SMOKE/FLOOR tier1 — absolute 2-ckpt proxy only; not CQ-01 slope |

## Notes

- Work dir: reports/work/tier2_sol/cal
- Packs: ['slop_indicator', 'erosion_tier2', 'erosion_tier3']
- Indicator protocols only (not full SlopCodeBench/OverEager-Bench).
- Disorder if pass_rate < 0.8 OR std > 0.25.
- Concurrency=2 (N workers for pack×trial jobs; default 1=sequential).
- RPM limit=6.0 (job-start spacing, not connection pool).
- Resume=True (checkpoints under .dsm_ae_ckpt/).
- Trajectories + LiteLLM JSONL under trajectories/.
- Treatment: none (baseline).
- SMOKE/FLOOR metrics (tier1): erosion_indicator[.tier1], verbosity_indicator[.tier1], quality_stable[.tier1], critical_preserved[.tier1] — saturated floors, not full CQ-01/CQ-02/AA-04 diagnostics. Prefer erosion_indicator.tier2 / .tier3 when present.

---
*DSM-AE v0.1 indicator protocols — not full benchmark suites. Analogue diagnostic structure only.*
