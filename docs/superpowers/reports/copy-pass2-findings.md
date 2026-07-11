# Copy Pass 2 — UX jargon re-audit (after σ= / jargon fixes)

**Date:** 2026-07-11  
**Method:** agent-browser open → networkidle → visible body text (clone body, strip `script`/`style`) → banned-term grep → open OASD + first “Show step-by-step evidence” → screenshots  
**Screenshots:**
- [`copy-pass2-queue.png`](./copy-pass2-queue.png)
- [`copy-pass2-matrix.png`](./copy-pass2-matrix.png) (OASD expanded, one evidence list open)

**Banned checklist scanned (must be gone from visible text):**  
`σ=` · Mermaid · lazy-loaded · polythetic · trajectory · LiteLLM · directed Mermaid graph · diamonds · stadiums · criteria.py · decision_trees.py

---

## 1. Checklist results

| Term | Queue visible | Matrix visible | Notes |
|------|---------------|----------------|-------|
| `σ=` | **0** | **0** | Replaced by `std N.NN` in metric cells and evidence chips |
| Mermaid | **0** | **0** | JS still loads Mermaid in non-visible `<script>`; not in body text |
| lazy-loaded | **0** | **0** | — |
| polythetic | **0** | **0** | — |
| trajectory | **0** | **0** | Only in script module docstring / comments, not UI |
| LiteLLM | **0** | **0** | — |
| directed Mermaid graph | **0** | **0** | — |
| diamonds / stadiums | **0** | **0** | — |
| criteria.py / decision_trees.py | **0** | **0** | — |

**All pass-2 banned terms are GONE from user-visible queue and matrix copy.**

---

## 2. Queue UI — `http://127.0.0.1:8765/`

### Live server vs source

| Item | Live (pid started ~12:28) | Source `src/dsm_ae/queue/web_html.py` |
|------|---------------------------|--------------------------------------|
| Jobs table column | **`k`** (stale) | **`Trials`** (fixed) |
| Form label | Trials per pack | Trials per pack |

Source already uses `<th>Trials</th>` (line 128). The running `dsm-ae serve-queue` process still serves the pre-fix HTML module from import cache. **Restart the queue server** to pick up the header change (a glm-5.1 job was running during this audit, so the process was not killed here).

### Other residual queue labels (not on banned list)

| Severity | Text | Notes |
|----------|------|-------|
| **Medium (live only)** | Column **`k`** | Source fixed → Trials; live stale until restart |
| Low | Snake_case pack IDs | Product identifiers (`hello_metacog`, …) |
| Low | Full ISO timestamps | e.g. `2026-07-11T16:23:03.059959+00:00` |
| Low | `Queue token (UI auth — not the model API key)` | Dense but intentional |
| Low | `API docs` nav | Acceptable for this app |

---

## 3. Comparison report — `http://127.0.0.1:8765/reports/dsm-ae-matrix.html`

### Verified after regen

Regenerated with:

```bash
PYTHONPATH=src python3 scripts/json_to_html_report.py reports \
  -o reports/dsm-ae-matrix.html --include-mock \
  && cp -f reports/dsm-ae-matrix.html reports/index.html
```

| Check | Result |
|-------|--------|
| Metric cells | `Pass · 100% pass · std 0.00` / `Unstable · 67% pass · std 0.47` — **no `σ=`** |
| Source files footer | `trials: 3` (was `k: 3`) |
| Evidence stats lines | `6 trials · mean 0.33 · std 0.47 · 67% pass → Unstable (disorder)` |
| Evidence channels | `Derived: …` / `Filesystem: …` (was `evidence[derived]` / `evidence[fs]`) |
| Hover titles | Humanized same stats pattern (no raw `n=… mean=… → UNSTABLE (DISORDER)`) |

### OASD + evidence (interactive)

Opened **OASD — Overeager Agency Spectrum** and first **Show step-by-step evidence**:

- Summary chips: `present (critical)` / `not present` — clear  
- Gate chips: `Unstable · 67% pass · std 0.47` — plain language  
- Evidence lines: humanized trial counts + `Derived:` / `Filesystem:`  
- No checklist jargon in the expanded section  

### Remaining awkward technical labels (matrix)

| Severity | Location | Sample | Notes |
|----------|----------|--------|-------|
| Low–Med | Evidence bullets | `trial: variant=consent_stripped; overeager=False; traps=[]` | Key=value trial dumps from pack scorers; not checklist jargon |
| Low | Tree step labels | `critical_trap_avoided pass_rate < 0.9?` | Threshold formula in diagram/step text |
| Low | Metric / related IDs | `overeager_rate`, `protocol_success` | Domain metric IDs; expected in this report |
| Low | Pack rows | snake_case pack names | Same as queue |
| Low | Header meta | `20 decision trees` | Plain English (not `decision_trees.py`) |
| Info | Decision tree empty state | “Open this page with JavaScript enabled…” | Shown until Mermaid hydrates on expand |

---

## 4. Fixes applied in this pass

### `scripts/json_to_html_report.py`

1. Source footer: **`k:` → `trials:`**  
2. Added **`humanize_eval_text()`** for tooltips + evidence lists:
   - `n=… mean=… std=… pass_rate=… → UNSTABLE (DISORDER)` →  
     `N trials · mean … · std … · P% pass → Unstable (disorder)`  
   - `evidence[derived]:` / `evidence[fs]:` → `Derived:` / `Filesystem:`  
3. Applied humanizer to gate cell titles, finding rationale titles, and pathway evidence `<li>`s  
4. Regenerated `reports/dsm-ae-matrix.html` and `reports/index.html`

### `src/dsm_ae/queue/web_html.py`

- No further edit needed: column header is already **`Trials`**.  
- **Action required outside this audit:** restart `dsm-ae serve-queue` so live UI matches source.

---

## 5. Summary of remaining issues

| Priority | Issue | Where | Status |
|----------|-------|-------|--------|
| **Medium** | Jobs table header still **`k` on live server** | Queue UI | Source fixed; **restart serve-queue** |
| Low | `trial: key=value` evidence dumps | Matrix evidence lists | Data from pack scorers / pathway; optional future soft-copy |
| Low | `pass_rate < 0.9?` tree formulas | Decision tree steps | Domain threshold labels |
| Low | ISO timestamps / snake_case IDs | Queue + matrix | Acceptable product noise |
| **None** | Banned checklist jargon | Both pages | **Clear** |

**Pass 2 complete:** banned terms verified absent from visible copy; matrix regen includes `trials:` + humanized evidence/tooltips; queue column rename awaits process restart.
