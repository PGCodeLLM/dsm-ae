# Copy Pass 1 — Visual UX jargon audit

**Date:** 2026-07-11  
**Method:** agent-browser open → wait 1s → interactive snapshot → visible body-text eval (excluding `script`/`style`) → jargon scan → screenshots  
**Screenshots:**
- [`copy-pass1-queue.png`](./copy-pass1-queue.png)
- [`copy-pass1-matrix.png`](./copy-pass1-matrix.png)

**Jargon checklist scanned:** Mermaid, lazy-loaded, polythetic, trajectory, LiteLLM, pack×, bootstrap, directed graph, diamonds, stadiums, criteria.py, decision_trees, startOnLoad, flowchart, FPG, σ=

---

## 1. Queue UI — `http://127.0.0.1:8765/`

### Checklist terms
**None of the checklist jargon terms appear in user-visible queue copy.**

### Other user-visible technical / meta labels (secondary)

| Severity | Location | Text | Notes |
|----------|----------|------|-------|
| Medium | Jobs table column header | **`k`** | Cryptic single-letter header. Aligns with “trials per pack” in the form but never spelled out. Users must infer that `k` = trials. |
| Low | Jobs table / form | Snake_case pack IDs (`hello_metacog`, `gate_discipline`, …) | Expected product identifiers; not checklist jargon. |
| Low | Nav | `API docs` | Fine for this app; slightly developer-facing. |
| Low | Form label | `Queue token (UI auth — not the model API key)` | Explicitly technical; appropriate for auth, but dense. |
| Low | Created column | Full ISO timestamps (`2026-07-11T16:23:03.059959+00:00`) | Machine format in primary UI. |

### Clean / good
- H1 + subtitle are plain language (“Add a model, choose packs…”).
- Form fields use human labels (“Trials per pack”, “Parallel trials”, “Evaluation packs”).
- No Mermaid / flowchart / LiteLLM / σ / polythetic / trajectory leakage.

---

## 2. Comparison report — `http://127.0.0.1:8765/reports/dsm-ae-matrix.html`

### Checklist hits (user-visible)

| Severity | Term | Where | Count / sample | Recommendation |
|----------|------|-------|----------------|----------------|
| **High** | **`σ=`** | Metric results table cells | **821** cells, e.g. `Pass · 100% pass · σ=0.00`, `Unstable · 33% pass · σ=0.47 · disorder` | Replace with plain language: **“std 0.00”**, **“spread 0.00”**, or drop from the cell and keep stats in hover only. Inconsistent with evidence panels which already say **`std 0.47`**. |
| — | Mermaid | *Not visually shown* | Hidden `script.mermaid-src` (`display:none`) + injected `<style>` (0×0 box) | **No visual issue.** Dom contains `flowchart TD` source and `#mermaid-…` CSS, but not painted. Flag only if copy/select-all or a11y tree surfaces it. |
| — | flowchart | Same as Mermaid | In hidden scripts / CSS class names | Not user-visible. |
| — | lazy-loaded, polythetic, trajectory, LiteLLM, pack×, bootstrap, directed graph, diamonds, stadiums, criteria.py, decision_trees, startOnLoad, FPG | — | **0 visible hits** | Clear. |

### Syndrome details (opened: **OASD — Overeager Agency Spectrum**)

**Visible structure (good):**
- Summary chip list of models: `present (critical)` / `not present`
- “Expand to view the decision tree for OASD.”
- Related metrics as code-ish IDs: `overeager_rate`, `critical_trap_avoided`, `scope_safe` (metric IDs — domain, not checklist jargon)
- Rendered tree labels are readable English: “Begin OASD algorithm”, “All indicator metrics available?”, “PRESENT — Overeager Agency Spectrum (critical)”
- Section “How each model was scored” + “Show step-by-step evidence”

**Evidence panel technical meta (not on checklist, but user-facing when expanded):**

| Severity | Sample | Notes |
|----------|--------|-------|
| Medium | `overeager_rate UNSTABLE · 67% pass · std 0.47` | OK-ish; uses `std` not `σ` |
| Medium | `n=6 mean=0.333 std=0.471 pass_rate=0.667 → UNSTABLE (DISORDER)` | Raw evaluator dump; dense stats + ALL-CAPS states |
| Medium | `evidence[derived]: overeager — False`, `evidence[fs]: .env.old — kept` | Bracketed evidence channel tags feel like debug output |
| Low | Tree node: `pass_rate < 0.9?` | Threshold formula in diagram label |

### Hover tooltips (metric cells)
Hover titles expose the same raw line as evidence, e.g.:

> `n=3 mean=0.667 std=0.471 pass_rate=0.667 → UNSTABLE (DISORDER). e.g. Mood section present=True; …`

This is **user-reachable** (instruction text says “Hover a cell for a short explanation”) but is **not** a short explanation—it's evaluator telemetry.

### Other secondary copy notes

| Severity | Location | Text | Notes |
|----------|----------|------|-------|
| Low | Header meta | `14 model(s) · 19 pack(s) · 62 metric(s) · 20 syndrome(s) · 20 decision trees` | “decision trees” is plain English (not `decision_trees`); fine. |
| Low | Source files | `k: 3; sources: reports/full-suite/….json` | Same cryptic **`k`** as queue; paths are expected in a “Source files” footer. |
| Low | Legend | `Pass / ran / not present` etc. | Clear. |
| Info | Metric row labels | `task_answered [22,68]` | Metric ID + citation nums; acceptable for this report type. |

---

## 3. Summary of issues to fix (priority)

1. **[High] Metric table: replace `σ=` with plain wording** (or omit from dense cell string). ~821 occurrences. Align with evidence’s `std`.
2. **[Medium] Queue + Source files: rename column/label `k` → “Trials”** (or “Trials per pack”) so it matches the form.
3. **[Medium] Hover titles + evidence lines:** soften `n=… mean=… std=… pass_rate=… → UNSTABLE (DISORDER)` into a short human sentence; keep raw stats secondary.
4. **[Low] Evidence tags** `evidence[derived]` / `evidence[fs]` → “Derived:” / “Filesystem:” if still shown to end users.
5. **[None on checklist]** Mermaid / flowchart / polythetic / trajectory / LiteLLM / pack× / bootstrap / directed graph / diamonds / stadiums / criteria.py / decision_trees / startOnLoad / FPG / lazy-loaded — **not user-visible** on these two pages.

---

## 4. Pages not fully interactive-tested
- Only one syndrome section expanded (OASD); other syndrome trees use the same Mermaid + evidence pattern.
- Queue “New evaluation” pack multi-select open state not separately screenshotted (pack IDs visible in closed label + table).

**Pass 1 complete.**
