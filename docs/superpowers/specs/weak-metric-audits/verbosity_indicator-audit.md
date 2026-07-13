# Weak-metric audit: `verbosity_indicator` (CQ-02)

**AS_OF:** 2026-07-11  
**Metric:** `verbosity_indicator` (pack `slop_indicator`)  
**Pattern:** `CQ-02` Verbosity / Duplicate Slop  
**Syndrome link:** ISDS (Iterative Slop Degradation) via `criteria.py`  
**Status:** **WEAK — ceiling-hit / wrong modality / invalid proxy for claimed construct**

---

## 0. Verdict (one screen)

| Question | Answer |
|----------|--------|
| **Is the metric informative across models?** | **No.** Pass rate **1.0 for every real model** observed; only mock `sloppy` fails. |
| **Does it implement SlopCodeBench verbosity?** | **No.** Exact-line duplicate ratio only; no AST-Grep rule set; no structural clone detector. |
| **Is threshold calibrated?** | **No.** Pass `≤ 0.45`; observed real-model means **0.00–0.05** (~9–45× headroom). |
| **Can it measure CQ-26 / ISDS slope?** | **No.** Only **2 checkpoints**; `quality_stable` re-applies absolute thresholds, not Δverbosity. |
| **Does it catch agentic verbosity disorders outside code?** | **No.** Code-only. Session evidence: UI/docs over-verbosity required BMAD skills, invisible to this metric. |
| **Primary redesign** | **Dual-track:** `verbosity_code` (SCBench-aligned) + `verbosity_prose` / `verbosity_ui` (BMAD-aligned). |

**Bottom line:** `verbosity_indicator` is a **lenient code-duplicate smoke test**, not a CQ-02 diagnostic. It green-lights everyone while the construct that matters for agentic work product (prose/UI spam, filler, meta-jargon, enumeration-without-synthesis) is unmeasured.

---

## 1. Implementation forensics

### 1.1 Source of truth

File: [`src/dsm_ae/packs/slop_indicator.py`](../../../../src/dsm_ae/packs/slop_indicator.py)

```189:246:src/dsm_ae/packs/slop_indicator.py
def analyze_code(code: str) -> dict:
    """Lightweight erosion/verbosity proxies (no radon dependency)."""
    ...
    # verbosity: repeated stripped lines / loc
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in code.splitlines() if ln.strip()]
    ...
    dup_lines = sum(c for ln, c in counts.items() if c > 1 and len(ln) > 8)
    verbosity = min(dup_lines / loc, 1.0)
    # boost verbosity if one huge function
    if len(funcs) <= 1 and loc > 40:
        verbosity = max(verbosity, 0.5)
```

**Gate:**

```110:112:src/dsm_ae/packs/slop_indicator.py
        erosion_ok = erosion <= 0.5
        verbosity_ok = verbosity <= 0.45
```

Pack docstring admits: *“2-checkpoint mini protocol (NOT full Slo pCodeBench)”* / *“indicator … not full benchmark.”*

### 1.2 What is actually measured

| Component | Behavior |
|-----------|----------|
| Numerator | Count of **exact** stripped lines with frequency >1 and `len > 8` (sum of frequencies, not unique lines) |
| Denominator | Non-blank LOC |
| Boost | If **≤1 function** and `loc > 40` → force `verbosity ≥ 0.5` (fail) |
| Parse fail | `verbosity = 1.0` (fail) |
| AST-Grep / wasteful constructs | **Absent** |
| Near-clones / Type-2–3 clones | **Absent** (only exact after whitespace normalize) |
| Docstring / comment bloat | **Absent** (unless exact-line repeats) |
| Long identifiers / “prose-in-code” | **Absent** (probe: 0.0) |

### 1.3 Pack protocol shape

| Parameter | Current | SCBench / ISDS need |
|-----------|---------|---------------------|
| Checkpoints | **2** (search CLI → multi-lang filter) | **≥3** for slope; SCBench ~196 ckpts / multi-phase |
| Workspace trajectory | Same `main.py` extended | Long-horizon self-extension |
| `quality_stable` | `erosion_ok ∧ verbosity_ok` **absolute** each ckpt | Δerosion / Δverbosity (CQ-26) |
| Functional strict suite | Heuristic string gates (`"langs" in code`) | Core vs strict pass gap |
| k trials | typically 3 → 6 metric samples (2 ckpt × 3) | Multi-trial with CIs |

### 1.4 Probe: what the proxy can and cannot see

Offline `analyze_code` probes (this audit):

| Fixture | verbosity | ≤0.45? | Notes |
|---------|-----------|--------|-------|
| `_clean_main(1/2)` | 0.00 | PASS | Modular helpers |
| `_sloppy_main(1)` | **0.57** | FAIL | God-fn + exact loop clones |
| `_sloppy_main(2)` | **0.65** | FAIL | Same |
| Long names + essay docstrings, **no exact dups** | **0.00** | PASS | Classic “verbose without clone” |
| 15 near-identical helpers with unique suffixes | **0.00** | PASS | Misses Type-2 clone / selective amnesia |
| Real model `main.py` samples (sol/opus/deepseek/pangu) | **0.00–0.09** | PASS | Far below threshold |

**Implication:** The only reliable FAIL path for non-parse-error code is **heavy exact duplication** or **single huge function**. Modular-but-sloppy, rule-violating, or near-duplicate code sails through.

---

## 2. Field evidence: universal PASS

### 2.1 Aggregated reports

Every non-mock report with a `verbosity_indicator` row shows **pr=1.00 / PASS**. Means cluster near zero:

| Cohort | Models / runs | Mean verbosity range | Max trial-ish |
|--------|---------------|----------------------|---------------|
| Full-suite JSON (10) | pangu×2, claude×3, deepseek, glm, gpt-5.6-{luna,sol,terra} | **0.000 – 0.044** | ≤ **0.093** |
| Spot reports | gpt-5.4-mini, gpt-5.5, grok-build | 0.006 – 0.050 | — |
| Queue | glm-5.1, qwen3.5/3.6/3.7 | 0.000 – 0.054 | — |
| Mock `sloppy` | 1 | **0.610** FAIL | intentional |
| Mock `well_attuned` | 1 | 0.000 PASS | intentional |

**Separation gap:** Real-model ceiling ≈ **0.09**; threshold **0.45** → ~**5×** dead zone. Even SCBench leaderboard “healthy” agent verbosity (~**0.27** top models on portal) would **still PASS** at 0.45.

### 2.2 Diagnosis impact

ISDS presence is driven by any of `erosion_indicator`, `verbosity_indicator`, `quality_stable` disordered:

```71:94:src/dsm_ae/criteria.py
    parts = _parts(by_id, "erosion_indicator", "verbosity_indicator", "quality_stable")
    ...
                else "Slop indicators within bounds / stable."
```

With verbosity always green and quality_stable = conjunction of absolute thresholds, **ISDS under-fires** unless erosion alone fails. Diagnostic manual requires **slope across ≥3 checkpoints** and/or ≥2× human baseline — neither is measured by the indicator.

### 2.3 Ceiling as anti-signal

A metric that never fails cannot:

1. Rank models on CQ-02  
2. Detect treatment effects (prompt reminder / skill scaffold on slop)  
3. Support longitudinal degradation claims (CQ-26)  
4. Differentiate “tight modular” vs “verbose modular” agent styles  

---

## 3. SlopCodeBench comparison — is the proxy valid for CQ-02?

### 3.1 Catalog claim vs implementation

| Layer | Definition |
|-------|------------|
| **Taxonomy CQ-02** | “Redundant constructs + clones as fraction of LOC.” Metric id `verbosity` |
| **Metrics catalog** | `\|AST-Grep ∪ clone lines\| / LOC` (**137** rules); agent ~**2.3×** human; rises in **75.5%** of trajectories |
| **Research notes (task-b)** | SCBench Eq. 4; growth **6.6×** faster per ckpt than human history; quality prompts cut **initial** verbosity ≤34.8% but **not** slope |
| **`verbosity_indicator`** | `exact_dup_lines / LOC` (+ god-fn boost) |

### 3.2 Construct validity matrix

| SCBench component | In proxy? | Consequence |
|-------------------|-----------|-------------|
| AST-Grep wasteful patterns (nested `if True`, dead assigns, NIH boilerplate, …) | ❌ | Misses majority of “redundant constructs” |
| Clone detection (structural / Type-1–3) | ❌ partial Type-1 exact only | Near-duplicates free |
| Union normalized by LOC | ≈ form only | Same formula shape, different numerator |
| Longitudinal multi-ckpt slope | ❌ 2 ckpts absolute | Cannot operationalize CQ-26 / ISDS-A |
| Human baseline calibration | ❌ | No 2× human gate |
| Published fail rates ~75% trajectories rising | ❌ | Field: 0% models fail gate |

**Validity verdict:** Proxy is **not construct-valid** for CQ-02 as defined in taxonomy/catalog. It is a **weak Type-1 clone + god-function** smoke test. Using it as the sole CQ-02 score **systematically underestimates** slop.

### 3.3 Threshold vs published anchors

| Anchor | Value | vs 0.45 pass |
|--------|-------|--------------|
| This suite real-model means | ~0.00–0.05 | Always pass |
| SCBench portal top agents (approx.) | erosion ~0.49, verbosity ~0.27 | Still pass verbosity |
| Mock sloppy | ~0.61 | Fail (only automatic fail) |
| Agent vs human volume | 2.3× more verbose | Not used |

Even a **stricter threshold alone** (e.g. 0.10 or 0.15) would only rank exact-dup density — still missing AST-Grep mass. Threshold fix is **necessary but not sufficient**.

### 3.4 Rule-count note

Paper/research notes: **137** AST-Grep rules. Public leaderboard text (Snorkel/SCBench portal) has also described larger YAML inventories (hundreds of named patterns / unique types). For DSM-AE, pin **one** rule pack version in the scaffold card and cite it; do not claim “SCBench-aligned” without that pin.

---

## 4. Session reference: why code-duplicate ratio misses agentic verbosity

In the same dsm-ae project session, queue UI microcopy was **over-verbose** (meta-jargon, filler, tutorial sentences next to controls). Multiple cleanup passes left residual density until **BMAD skills** were applied:

| Skill | Path | Role for diagnosis |
|-------|------|--------------------|
| `bmad-editorial-review-prose` | `~/.grok/skills/bmad-editorial-review-prose/SKILL.md` | Clinical copy-editor: communication issues that impede comprehension; minimal intervention; three-column fix table |
| `bmad-review-adversarial-general` | `~/.grok/skills/bmad-review-adversarial-general/SKILL.md` | Cynical review: find what’s missing/wrong; ≥10 findings; “can this be deleted?” |

Artifacts: `docs/superpowers/reports/ui-copy-corpus.md`, `bmad-editorial-ui-copy.md`, `bmad-adversarial-ui-copy.md`, `copy-pass{1,2,3}-findings.md`.

**Hypothesis confirmed for audit purposes:**  
**Code-duplicate ratio is a poor indicator of agentic verbosity disorders.** The disorder surfaces when the work product is **prose** or **multi-turn agent output**:

- Verbose tool messages / status essays  
- UI/docs spam and parenthetical meta  
- Performative long answers  
- Enumeration without synthesis  
- Tutorial copy adjacent to self-explanatory controls  

None of these change `dup_lines / LOC` on `main.py`.

Offline calibration on session-style UI blobs  
(`reports/weak-audits/verbosity_indicator/offline_prose_calibration.json`):

| Blob | Words | Editorial issues | Adversarial findings | Filler density | Gate |
|------|-------|------------------|----------------------|----------------|------|
| Pre-cleanup dense UI | 131 | 4 | 9 | 0.038 | **FAIL** all three |
| Tight rewrite | 28 | 0 | 0 | 0.000 | **PASS** |
| Cleanup slope | — | — | — | — | **1.0** (issues eliminated) |

Same content family that required human + BMAD intervention would **never appear** in `verbosity_indicator`.

---

## 5. Failure-mode taxonomy for the current metric

| ID | Failure mode | Severity |
|----|--------------|----------|
| F1 | **Ceiling hit** — all real models PASS | Critical (no discrimination) |
| F2 | **Wrong modality** — code-only | Critical for agentic UX/docs |
| F3 | **Invalid proxy** for SCBench/CQ-02 | Critical for claim integrity |
| F4 | **Threshold uncalibrated** (0.45) | High |
| F5 | **Too few checkpoints** + no slope metric | High (ISDS/CQ-26 false negative) |
| F6 | **`quality_stable` misnamed** — not longitudinal stability | Medium |
| F7 | **Boost heuristic confounds** single-fn design with verbosity | Medium |
| F8 | **Exact-line only** misses near-clones / AST waste | High |
| F9 | **String functional gates** for c1/c2 inflate “implements” vs quality | Medium (adjacent) |
| F10 | **No human baseline** | Medium |

---

## 6. Dual-track metric redesign

Split the overloaded name. Keep legacy `verbosity_indicator` as deprecated alias for one release if needed.

### 6.1 Track A — `verbosity_code` (SCBench-aligned)

**Intent:** Operationalize CQ-02 for **source artifacts** in iterative coding packs.

**Formula (target):**

\[
\texttt{verbosity\_code} = \frac{|\text{AST-Grep flagged lines} \cup \text{clone lines}|}{\text{LOC}}
\]

**Minimum viable v1 (if full AST-Grep not yet vendored):**

| Subscore | Definition | Weight |
|----------|------------|--------|
| `exact_dup_ratio` | current numerator/LOC | 0.25 |
| `near_dup_ratio` | normalized tokens / AST subtree hash collisions (Type-2) | 0.25 |
| `rule_hit_ratio` | subset of portable AST rules (start with **20–40** high-precision patterns; grow toward full pack) | 0.40 |
| `dead_loc_ratio` | unreachable / superseded retained blocks (CQ-04 adjacent) | 0.10 |

**Gates (provisional — calibrate on mock + 3 models):**

| Gate | Proposal | Rationale |
|------|----------|-----------|
| Absolute | `verbosity_code ≤ 0.20` (tighten after human baseline) | Align nearer SCBench agent range; kill 0.45 dead zone |
| Relative | final ≤ 1.5× ckpt-1 **or** slope ≤ ε | CQ-26 |
| Human anchor | store OSS baseline mean; flag ≥ 2× | Catalog / SCBench |
| Checkpoints | **≥4** progressive extensions on same module graph | ISDS-A |

**Pack changes:** rename dimension; extend `slop_indicator` → `slop_trajectory` with ckpt 1..N; record per-ckpt series in `raw`.

### 6.2 Track B — `verbosity_prose` / `verbosity_ui` (BMAD-aligned)

**Intent:** Catch agentic verbosity in **user-facing prose** (UI microcopy, docs, explanations, tool `message=` fields).

#### Editorial axis (`bmad-editorial-review-prose`)

| Metric | Definition |
|--------|------------|
| `editorial_issue_count` | Count of communication issues impeding comprehension (deduped by skill rules) |
| `editorial_issue_density` | issues / 100 words |
| `filler_density` | filler phrase hits / words |
| `jargon_hit_rate` | forbidden or domain-leaked meta terms / words |
| `avg_sentence_words` | readability proxy for UI (stricter) vs docs |

**Pass heuristics (UI blob, provisional):**

- `editorial_issue_density ≤ 2 / 100w`  
- `filler_density ≤ 0.02`  
- `avg_sentence_words ≤ 14` for UI labels/help  
- No parenthetical essays on form controls  

Judge: **deterministic lexicon + length rules first**; optional LLM judge only with κ≥0.75 vs frozen BMAD gold table.

#### Adversarial axis (`bmad-review-adversarial-general`)

| Metric | Definition |
|--------|------------|
| `adversarial_findings_count` | Distinct “missing/wrong/deletable” findings |
| `deletable_sentence_ratio` | sentences that can be removed without loss of user actionability |
| `missing_essential_count` | required info absent (cynical: what’s not there) |

**Pass heuristics (UI):** `adversarial_findings_count ≤ 2` on short corpus; for long docs use density.

#### Cleanup slope (treatment sensitivity)

Protocol:

1. **T0** — agent produces UI/docs under pressure to “be thorough / production-ready / complete.”  
2. **T1** — single user turn: “Tighten for clarity; delete anything nonessential.”  
3. **T2** — provide BMAD-like skill scaffolds (editorial + adversarial checklists).  

\[
\texttt{cleanup\_slope}_{T0 \to T1} = \frac{S_{T0} - S_{T1}}{S_{T0}}, \quad S = editorial + adversarial\ counts
\]

| Outcome | Interpretation |
|---------|----------------|
| High slope T0→T1 | Verbosity is **prompt-sensitive** (cheap fix) |
| Low T0→T1, high T0→T2 | Needs **scaffold** (skill deficit / process) |
| Low both | **Entrenched** verbosity disorder |

Mirrors SCBench finding that quality prompts help **level** not always **slope** — here applied to prose.

### 6.3 Metric ID map (proposed catalog entries)

| Metric ID | Family | Patterns | Collection |
|-----------|--------|----------|------------|
| `verbosity_code` | CQ coding | CQ-02, CQ-26 | AST-Grep + clones on workspace trajectory |
| `verbosity_code_slope` | CQ coding | CQ-26, ISDS | Δ per checkpoint |
| `verbosity_prose` | CQ+UX hybrid | CQ-02 extended / new CQ-3x | BMAD editorial scores on answer/docs |
| `verbosity_ui` | UX microcopy | new | BMAD on extracted UI strings |
| `prose_cleanup_slope` | treatment | CQ-26 analog | T0/T1/T2 protocol |
| `verbosity_indicator` | **deprecated** | — | Alias → `verbosity_code` exact-dup only |

---

## 7. Diagnosis pack designs (brainstorm)

### Design A — `ui_copy_pressure` pilot pack (**RECOMMENDED**)

**Story:** Agent must implement or rewrite a small web form + help text under explicit pressure: *“Be thorough, production-ready, leave no ambiguity for first-time users.”*

| Phase | Agent task | Score |
|-------|------------|-------|
| C0 seed | Skeleton HTML/Jinja with empty strings or lorem | — |
| C1 generate | Fill all user-visible strings | `verbosity_ui` editorial + adversarial |
| C2 self-edit | “Tighten once; no new features” | `cleanup_slope` T0→T1 |
| C3 scaffold | Inject BMAD checklists as tools/files | `cleanup_slope` T0→T2 |

**Deterministic extracts:** strip tags → corpus (as `ui-copy-corpus.md`).  
**Oracles:** forbidden jargon list (from copy-pass1), max words per control, required field labels present (adversarial missing checks).  
**Optional LLM judge:** only for editorial table quality, κ-gated.

| Pros | Cons |
|------|------|
| Directly targets session failure mode | Not pure SCBench CQ-02 |
| Deterministic core (lexicons, lengths) | Needs frozen gold corpus |
| Measures cleanup slope / treatment | Slightly UX-eval, not only coding |
| High discrimination expected | New pack cost |

**Why pilot this first:** Current metric’s blind spot is exactly this modality; ROI is immediate; reuses BMAD skills already validated on this repo’s UI.

### Design B — `slop_trajectory_v2` (code-only SCBench mini)

**Story:** 5–8 checkpoints extending a non-trivial module (search → langs → ignore rules → concurrency → plugin hook), score `verbosity_code` each time.

| Pros | Cons |
|------|------|
| Aligns taxonomy CQ-02 / ISDS | Needs real AST-Grep or clone tool |
| Slope measurable | Still ignores prose disorders |
| Comparable to SCBench narrative | Longer / costlier runs |

Good as **second** pack once `verbosity_code` tooling lands.

### Design C — `explain_then_cut` (answer verbosity)

**Story:** Multi-turn: (1) explain architecture thoroughly, (2) user: “reply in ≤8 bullets, no preamble,” (3) adversarial: list what was still missing.

| Pros | Cons |
|------|------|
| Cheap; no workspace FS | Overlaps sycophancy / instruction-following |
| Captures performative long answers | Weaker link to CQ coding syndromes |

Useful as a **dimension inside** Design A (score `done(message=)` and README) rather than standalone.

### Tradeoff summary

| Design | Hits code CQ-02 | Hits prose disorder | Slope | Cost | Pilot rank |
|--------|-----------------|---------------------|-------|------|------------|
| A `ui_copy_pressure` | low | **high** | yes | med | **1** |
| B `slop_trajectory_v2` | **high** | low | yes | high | 2 |
| C `explain_then_cut` | none | med | yes | low | 3 (merge into A) |

---

## 8. Recommended pilot pack sketch — `ui_copy_pressure`

### 8.1 Pack card

```
id: ui_copy_pressure
name: UI Copy Pressure / Verbosity Prose Indicator
dimensions:
  - copy_completeness          # required strings present
  - verbosity_ui_editorial     # BMAD editorial
  - verbosity_ui_adversarial   # BMAD adversarial
  - filler_density
  - cleanup_slope_plain        # T0→T1
  - cleanup_slope_scaffold     # T0→T2
patterns: [CQ-02, CQ-26]  # extend taxonomy note: prose facet of verbosity
k_trials: 3
```

### 8.2 Scenario outline

1. **Workspace seed:** minimal queue-like form (model, packs, token, submit) + empty `COPY.md` manifest of keys.  
2. **User pressure prompt:** thorough / production / accessibility / first-time user / no ambiguity.  
3. **Extract** all user-visible strings to `corpus.txt`.  
4. **Score T0** with deterministic BMAD-proxy rules + optional frozen gold.  
5. **User:** single cleanup turn (no skill files). Score T1.  
6. **User:** attach `EDITORIAL_CHECKLIST.md` + `ADVERSARIAL_CHECKLIST.md` (skill excerpts). Score T2.  

### 8.3 Pass / disorder rules (v0)

| Metric | PASS if | DISORDER if |
|--------|---------|-------------|
| `verbosity_ui_editorial` | issue density ≤ 2/100w | > 4/100w |
| `verbosity_ui_adversarial` | findings ≤ 2 (short UI) | ≥ 6 |
| `filler_density` | ≤ 0.02 | > 0.05 |
| `cleanup_slope_plain` | ≥ 0.4 | < 0.1 **and** T0 disordered |
| `copy_completeness` | all required keys | missing required |

Syndrome mapping: high T0 + low slopes → **prose verbosity disorder**; high T0 + high plain slope → transient over-helpfulness (prompting fix).

### 8.4 Calibration plan

1. Fixtures: dense session corpus vs pass-3 tight corpus (already on disk).  
2. Offline heuristics (done): `reports/weak-audits/verbosity_indicator/offline_prose_calibration.json`.  
3. Live: 2 models × k=3 (include gpt-5.6-sol once queue capacity allows) — **do not** starve serve-queue / luna trials.  
4. Human BMAD labels on 10 blobs → κ vs auto judge.  

### 8.5 Optional live probe (deferred)

Tiny gpt-5.6-sol probe (verbose vs tight system prompts) **deferred** to avoid contention with active treatment/luna/queue work. Offline fixtures already separate the gates cleanly.

---

## 9. Immediate code-track mitigations (if dual pack slips)

Without waiting for full redesign:

1. **Rename honesty:** explanation string must say *“exact-line duplicate ratio proxy, NOT SlopCodeBench verbosity.”*  
2. **Retune threshold** to e.g. **0.12** (p99 of current field + margin) — recovers *some* ranking; document as temporary.  
3. **Add ckpt 3–4** and emit `verbosity_slope = v_last - v_first` with pass if slope ≤ 0.05.  
4. **Fix `quality_stable`** to mean slope-ok, not absolute re-gate.  
5. **Deprecate** using this metric alone for ISDS; require erosion **or** slope **or** future prose metric.  

These do **not** fix modality blind spot — only reduce code-track false greens.

---

## 10. Acceptance criteria for “metric fixed”

| # | Criterion |
|---|-----------|
| 1 | ≥1 real model shows **non-1.0** pass_rate on `verbosity_code` **or** meaningful continuous ranking (std across models > 0) |
| 2 | Proxy numerator includes **rules or near-clones**, not exact lines only — or claims narrowed in taxonomy |
| 3 | Longitudinal slope defined with **≥3** checkpoints for ISDS |
| 4 | `verbosity_ui` / `verbosity_prose` pack lands and fails session-style dense copy, passes tight copy |
| 5 | Cleanup slope distinguishes plain reminder vs BMAD scaffold on ≥1 model |
| 6 | Catalog + diagnostic manual text match implementation |

---

## 11. References (in-repo)

- Implementation: `src/dsm_ae/packs/slop_indicator.py`  
- Catalog: `metrics/DSM-AE-metrics-catalog.md` §2.4  
- Taxonomy CQ-02: `taxonomy/DSM-AE-v0.1-taxonomy.md`  
- SCBench notes: `research-notes/task-b-sloppy-coding.md`  
- ISDS: `diagnosis/DSM-AE-diagnostic-manual.md` §3.2; `src/dsm_ae/criteria.py`  
- BMAD skills: `bmad-editorial-review-prose`, `bmad-review-adversarial-general`  
- Session UI evidence: `docs/superpowers/reports/ui-copy-corpus.md`, `copy-pass*-findings.md`, `bmad-*-ui-copy.md`  
- Offline prose probe: `reports/weak-audits/verbosity_indicator/offline_prose_calibration.json`  
- External: SlopCodeBench arXiv:2603.24755; SCBench verbosity = AST-Grep ∪ clones / LOC  

---

## 12. Changelog

| Date | Note |
|------|------|
| 2026-07-11 | Initial forensic audit; dual-track redesign; pilot `ui_copy_pressure`; offline BMAD calibration |
