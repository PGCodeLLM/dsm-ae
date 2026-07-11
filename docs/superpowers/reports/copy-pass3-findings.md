# Copy Pass 3 — FINAL visual verification (acceptance)

**Date:** 2026-07-11  
**Verdict: PASS**  
**Method:** `agent-browser --args "--no-sandbox,--disable-dev-shm-usage"`  
open → networkidle → accessibility snapshot + `get text body` + `eval` (open first syndrome details + first “Show step-by-step evidence”) → forbidden-phrase grep on **visible body text only** → screenshots  

**Screenshots:**
- [`copy-pass3-queue.png`](./copy-pass3-queue.png)
- [`copy-pass3-matrix.png`](./copy-pass3-matrix.png) (first syndrome **MCD** expanded; first **Show step-by-step evidence** opened in session)

**Scope:**
1. `http://127.0.0.1:8765/` — queue
2. `http://127.0.0.1:8765/reports/dsm-ae-matrix.html` — comparison report

No code edits required (no forbidden phrases remaining in visible UI).

---

## 1. Forbidden checklist (visible body only)

| Term / pattern | Queue | Matrix (collapsed) | Matrix (MCD + evidence open) | Result |
|----------------|-------|--------------------|------------------------------|--------|
| Mermaid | 0 | 0 | 0 | **PASS** |
| lazy-loaded | 0 | 0 | 0 | **PASS** |
| polythetic | 0 | 0 | 0 | **PASS** |
| trajectory | 0 | 0 | 0 | **PASS** |
| LiteLLM | 0 | 0 | 0 | **PASS** |
| pack× | 0 | 0 | 0 | **PASS** |
| bootstrap | 0 | 0 | 0 | **PASS** |
| directed graph | 0 | 0 | 0 | **PASS** |
| diamonds | 0 | 0 | 0 | **PASS** |
| stadiums | 0 | 0 | 0 | **PASS** |
| criteria.py | 0 | 0 | 0 | **PASS** |
| decision_trees | 0 | 0 | 0 | **PASS** |
| startOnLoad | 0 | 0 | 0 | **PASS** |
| flowchart (as prose) | 0 | 0 | 0 | **PASS** |
| σ= | 0 | 0 | 0 | **PASS** |
| `NOT RUN` (all-caps) | 0 | 0 | 0 | **PASS** (title case **Not run** only) |
| `PRESENT/` (all-caps slash labels) | 0 | 0 | 0 | **PASS** |

**Note (non-failing):** Raw HTML still embeds Mermaid JS (`mermaid.initialize`, `startOnLoad`, flowchart diagram source) for rendering decision trees. Those strings are **not** user-visible body copy. Diagnosis node labels use `PRESENT — …` / `ABSENT — …` (em dash), not forbidden `PRESENT/` slash labels.

**Allowed terms observed as intended:** metric code names (`protocol_success`, …), model ids, pack ids, `std`, `decision tree`, `expand to view` / `Expand to view`.

---

## 2. Queue — `http://127.0.0.1:8765/`

| Check | Result | Evidence |
|-------|--------|----------|
| Column header **Trials** (not **k**) | **PASS** | Snapshot: `columnheader "Trials" [ref=e20]`; screenshot shows **Trials** |
| Human meta / intro | **PASS** | “Add a model, choose packs, and run evaluations. Progress updates live while jobs run.” |
| Live-refresh meta | **PASS** | “This list refreshes every few seconds. Your form fields stay as you left them.” |
| No LiteLLM | **PASS** | Full body text scan |
| Form labels plain | **PASS** | “Trials per pack”, “Parallel trials”, “Queue token (UI auth — not the model API key)”, offline-demo help blurb |

**Pass-2 residual resolved:** live server previously showed stale column **`k`**; pass 3 live UI shows **`Trials`**.

---

## 3. Matrix — `http://127.0.0.1:8765/reports/dsm-ae-matrix.html`

### Intro / chrome (plain English)

| Element | Visible copy |
|---------|----------------|
| Title | DSM-AE Multi-Model Report |
| Meta line | Generated 2026-07-11 16:31 UTC · 14 model(s) · 19 pack(s) · 62 metric(s) · 20 syndrome(s) · 20 decision trees |
| Legend | Pass / ran / not present · Fail / present · Unstable · **Not run** |
| How-to | “Click a syndrome name or matrix cell to jump there. Expand a section to view its decision tree and how each model was scored.” |
| Pack coverage blurb | “Which evaluation packs each model completed.” |
| Matrix blurb | “Summary diagnoses across models. Click a cell to jump to that syndrome — expand to view the decision tree.” |
| Trees section | “Expand a syndrome to view its decision tree and the evidence for each model.” |

### First syndrome opened: **MCD — Meta-Cognitive Deficit**

- Summary chips: `present (moderate|severe)` / `not present` (sentence case)
- Helper: “Expand to view the decision tree for MCD.”
- Related metrics listed by id (allowed): `protocol_success`, `files_read_complete`, `project_specific_stops`
- Decision tree diagram renders with human questions (e.g. “All indicator metrics available?”) and Yes/No edges
- Section: “How each model was scored” / “Open a model’s evidence list to see the yes/no steps that led to the diagnosis.”

### First “Show step-by-step evidence” (Beta_pangu_505b)

Sample steps (no forbidden jargon):

1. Begin MCD algorithm  
2. Hello/metacog indicator metrics available? → YES  
3. Any protocol/files_read/stops gate disordered? → YES  
4. Any linked gate consistently FAIL (not merely UNSTABLE)? → NO  
5. PRESENT — Meta-Cognitive Deficit (moderate / unstable)  

Metric chips use `std 0.47` / `std 0.00` (not `σ=`). Trial notes use plain labels (`Filesystem: …`, composite trial blurbs).

---

## 4. Acceptance summary

| Surface | Status |
|---------|--------|
| Queue column **Trials**, human meta, no LiteLLM | **PASS** |
| Matrix intro plain English | **PASS** |
| First syndrome + first step-by-step evidence usable & clean | **PASS** |
| All forbidden visible-body phrases absent | **PASS** |

### Residual non-blocking notes (not fail criteria)

- Pack / metric / model identifiers remain snake_case or product ids (allowed).
- Job table timestamps remain full ISO UTC.
- Mermaid remains an implementation detail in non-visible script; UI never names it.
- Tree terminal labels may say `PRESENT —` / `ABSENT —` / `NOT EVALUATED` as diagnosis outcomes (distinct from banned `PRESENT/` and `NOT RUN`).

---

## Final verdict

**PASS** — copy acceptance criteria met on live queue and matrix; screenshots archived; no code changes needed.
