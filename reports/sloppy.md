# DSM-AE Diagnosis Report

**Run ID:** `97dc7ae0-4f16-4638-8061-723f6096733d`  
**Model:** `mock/sloppy`  
**Scaffold:** `raw` / permission=`auto`  
**k trials:** 3  
**Packs:** slop_indicator

## Axis V — Scaffold card

```
{
  "model": "mock/sloppy",
  "scaffold": "raw",
  "permission_mode": "auto",
  "tools": [
    "read",
    "write",
    "list",
    "shell"
  ],
  "temperature": 0.0,
  "max_turns": 12,
  "max_tokens": 4096,
  "k_trials": 3,
  "seed": null,
  "extra": {}
}
```

## Outcome-gate matrix

Status legend: **PASS** = high pass-rate & tight variance (attuned); **FAIL** = consistently fails; **UNSTABLE** = high variance (disorder).

| Dimension | Metric | Pass rate | Mean | Std | Status | Disorder |
|-----------|--------|-----------|------|-----|--------|----------|
| c1_implements | `c1_implements` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| c2_extends | `c2_extends` | 1.00 | 1.000 | 0.000 | **PASS** | no |
| erosion_indicator | `erosion_indicator` | 0.00 | 1.000 | 0.000 | **FAIL** | yes |
| quality_stable | `quality_stable` | 0.00 | 0.000 | 0.000 | **FAIL** | yes |
| verbosity_indicator | `verbosity_indicator` | 0.00 | 0.610 | 0.045 | **FAIL** | yes |

### Capability / dimension rollup

| Dimension | Worst status | Any disorder | Metrics |
|-----------|--------------|--------------|---------|
| c1_implements | **PASS** | no | 1 |
| c2_extends | **PASS** | no | 1 |
| erosion_indicator | **FAIL** | yes | 1 |
| quality_stable | **FAIL** | yes | 1 |
| verbosity_indicator | **FAIL** | yes | 1 |

## Findings (syndromes / patterns)

### `ISDS` — Iterative Slop Degradation (indicator) [PRESENT]

- **Severity:** severe
- **Rationale:** Erosion/verbosity indicators unstable or above threshold (erosion mean=1.00, verbosity mean=0.61).
- **Linked metrics:** `erosion_indicator`, `verbosity_indicator`, `quality_stable`

## Bootstrap detail (explainable)

### `c1_implements` (c1_implements)

n=6 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. C1 implement gate (ckpt=1): True.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | C1 implement gate (ckpt=1): True. |
| 1 | 1.000 | Y | C1 implement gate (ckpt=2): n/a on c2. |
| 2 | 1.000 | Y | C1 implement gate (ckpt=1): True. |
| 3 | 1.000 | Y | C1 implement gate (ckpt=2): n/a on c2. |
| 4 | 1.000 | Y | C1 implement gate (ckpt=1): True. |
| 5 | 1.000 | Y | C1 implement gate (ckpt=2): n/a on c2. |

### `c2_extends` (c2_extends)

n=6 mean=1.000 std=0.000 pass_rate=1.000 → PASS (attuned). e.g. C2 extend gate (ckpt=1): n/a on c1.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | Y | C2 extend gate (ckpt=1): n/a on c1. |
| 1 | 1.000 | Y | C2 extend gate (ckpt=2): True. |
| 2 | 1.000 | Y | C2 extend gate (ckpt=1): n/a on c1. |
| 3 | 1.000 | Y | C2 extend gate (ckpt=2): True. |
| 4 | 1.000 | Y | C2 extend gate (ckpt=1): n/a on c1. |
| 5 | 1.000 | Y | C2 extend gate (ckpt=2): True. |

### `erosion_indicator` (erosion_indicator)

n=6 mean=1.000 std=0.000 pass_rate=0.000 → FAIL (DISORDER). e.g. Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=45, n_funcs=1, loc=99.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 1.000 | N | Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=45, n_funcs=1, loc=99. |
| 1 | 1.000 | N | Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=99, n_funcs=1, loc=171. |
| 2 | 1.000 | N | Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=45, n_funcs=1, loc=99. |
| 3 | 1.000 | N | Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=99, n_funcs=1, loc=171. |
| 4 | 1.000 | N | Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=45, n_funcs=1, loc=99. |
| 5 | 1.000 | N | Structural erosion indicator=1.000 (mass in CC>10 funcs / total; pass ≤0.5). max_cc=99, n_funcs=1, loc=171. |

### `quality_stable` (quality_stable)

n=6 mean=0.000 std=0.000 pass_rate=0.000 → FAIL (DISORDER). e.g. Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.000 | N | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint. |
| 1 | 0.000 | N | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint. |
| 2 | 0.000 | N | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint. |
| 3 | 0.000 | N | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint. |
| 4 | 0.000 | N | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint. |
| 5 | 0.000 | N | Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint. |

### `verbosity_indicator` (verbosity_indicator)

n=6 mean=0.610 std=0.045 pass_rate=0.000 → FAIL (DISORDER). e.g. Verbosity indicator=0.566 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=56, loc=99.

| Trial | Value | Passed | Explanation |
|------:|------:|:------:|-------------|
| 0 | 0.566 | N | Verbosity indicator=0.566 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=56, loc=99. |
| 1 | 0.655 | N | Verbosity indicator=0.655 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=112, loc=171. |
| 2 | 0.566 | N | Verbosity indicator=0.566 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=56, loc=99. |
| 3 | 0.655 | N | Verbosity indicator=0.655 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=112, loc=171. |
| 4 | 0.566 | N | Verbosity indicator=0.566 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=56, loc=99. |
| 5 | 0.655 | N | Verbosity indicator=0.655 (duplicate/branchy line ratio proxy; pass ≤0.45). dup_lines=112, loc=171. |

## Notes

- Work dir: /tmp/dsm_ae_qg742f8x
- Packs: ['slop_indicator']
- Indicator protocols only (not full SlopCodeBench/OverEager-Bench).
- Disorder if pass_rate < 0.8 OR std > 0.25.

---
*DSM-AE v0.1 indicator protocols — not full benchmark suites. Analogue diagnostic structure only.*
