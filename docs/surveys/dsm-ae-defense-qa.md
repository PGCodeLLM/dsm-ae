# DSM-AE academic + industrial defense — adversarial Q/A

**AS_OF:** 2026-09-01  
**Purpose:** poke holes in the current framework *before* rewriting the blog or
claiming the snowball “created” the syndromes. Every answer is tagged
**IN-REPO** (supported by files/runs here) or **HOLE** (cannot be obtained
from existing experiment runs / methodology / codebase).

Compaction study is parked (`research-notes/compaction/PARKED.md`).

---

## 0. Chronology (do not rewrite this)

| When | What actually happened | Evidence |
|---|---|---|
| 2026-07-09 | Bibliography (88 sources), research-notes A–D, taxonomy v0.1 (**158 patterns**, 10 chapters), diagnostic manual | `sources/bibliography.md`, `taxonomy/DSM-AE-v0.1-taxonomy.md` AS_OF 2026-07-09, `research-notes/task-{a,b,c,d}-*.md` |
| 2026-07 | Mini indicator packs implemented from *seed* papers (OverEager, SlopCodeBench, MAST, AIRT, hello-protocol) | pack modules, blog §2.2, `reports/COVERAGE.md` |
| 2026-07-11 | Weak-gate audit: many metrics 100% PASS across 16 models | `docs/superpowers/specs/weak-metric-audits/EXECUTIVE_SUMMARY.md` |
| 2026-07-14 | Shared-syndrome repro: 7 packs × 2 models × **k=10** | `docs/repro-shared-symptoms/README.md` |
| 2026-08-28 | Literature snowball d≤3: **333 nodes**, mapped onto **already-named** packs; leftovers clustered | `research-notes/snowball/` |

**Consequence:** the snowball is a *retrospective mapping* of literature onto a
taxonomy that already existed. It is **not** how OASD / ISDS / TID / … were
first named. Any blog sentence of the form “we left groups unknown until N
sources named the same symptom, then minted the syndrome” is **false as
history**. It can be proposed as a **revalidation protocol** going forward.

---

## 1. Adversarial Q/A

### Q1. Was the survey a rigorous snowball?

**IN-REPO (partial).** The *August* snowball is documented and bounded:
seeds = every numbered bibliography entry + TACT; hop caps d1≤8 / d2≤5 /
d3≤3; keep only agentic-behaviour / tool-use / agent-alignment / agent-eval
cites; no invented citations; 333 nodes / 788 edges; 171 ship a benchmark
(`research-notes/snowball/PROCESS.md`, `FINDINGS.md`).

**HOLE.** The *July* taxonomy was **not** produced by that protocol. Notes
A–D are a conventional multi-source extract (18–23 sources each), not a
depth-3 citation tree with recorded exclude-reasons per hop. We do not have
an inter-rater κ, a PRISMA-style flow (identified → screened → excluded →
kept), or a second coder. MAST reports κ=0.88 on *their* traces; we have no
equivalent for our pattern coding.

**Defense that is honest:** cite the July notes as a **structured narrative
review** that *seeded* the taxonomy, and the August snowball as a
**replication / coverage audit** of that taxonomy against a larger citation
graph. Do not collapse the two into one method.

### Q2. How were references filtered into syndromes / metrics?

**IN-REPO.** Each taxonomy row has a **Source** column (OverEager, MAST,
AIRT, Vectara, SlopCodeBench, …). Metrics live in
`metrics/DSM-AE-metrics-catalog.md`. Packs declare which codes they wire
(`reports/COVERAGE.md`: **61 / 158 = 38.6%** wired). Polythetic rules are
code (`src/dsm_ae/criteria.py`: any disordered linked gate → PRESENT).

**HOLE.** There is no recorded inclusion rule of the form “keep a pattern
iff ≥N independent sources describe it **or** a named benchmark
operationalizes it.” Several codes are single-source or “practice”
(`AA-10` OverEager+practice; `PC-12` a $47k blog). Chapter 5 (SC, 35
patterns) mixes sycophancy benches, scheming papers, and chat-safety
(jailbreak / over-refusal) that the August cluster later marked **do not
promote** as coding-agent packs.

**Proposed revalidation (not yet run):** for each wired syndrome, publish
`(n_sources, n_benchmarks, n_incidents)` from `tree.json` and drop or
demote codes below a pre-registered N. August counts already exist per
*pack* (e.g. `eval_gaming_mini` 36, `tool_integrity` 29, `overeager_mini`
8) — that is the closest we have.

### Q3. Did syndromes “materialize” from unknown keyword clusters?

**HOLE as origin story. IN-REPO as a later audit.**

August: 187 unknown nodes → 8 clusters (`scheming`, `spec_drift`,
`jailbreak_refusal`, …). That *is* keyword/behaviour clustering of leftovers
**after** mapping onto existing packs. It discovered **gaps** (promote
scheming + spec_drift), not the original ten chapters.

The original 158 names were authored in July from notes A–D + seed papers.
`criteria.py` syndrome codes (OASD, ISDS, TID, …) were then attached to
pack gates. That is **construct-first, literature-anchored**, not
**open-coded-then-named**.

If the blog needs a clustering narrative, tell the truth in two layers:

1. **Construct layer (July):** seed benches + industry taxonomies (MAST 14
   modes, AIRT, OverEager, Slop) → 158 patterns → 10 chapters.
2. **Audit layer (August):** snowball → pack map → unknown cluster →
   candidate new chapters only if they survive N + benchmark.

### Q4. How is each symptom decomposed, and is that decomposition justified?

**IN-REPO.** Decomposition is **pack → deterministic gates → polythetic
OR**. Example OASD: `overeager_rate` ∨ `critical_trap_avoided` ∨
`scope_safe` (`criteria.py`). Determinism tags: `DET_EXACT`, `DET_TRACE`,
`DET_EXEC`, … (`docs/appendices/METRIC_ALGORITHMS.md`). No LLM-as-judge
in the mini battery (blog §2.2). Decision trees in
`src/dsm_ae/decision_trees.py` / Comparison tab.

**HOLE.**

- **OR-polythetic is maximally sensitive.** One weak gate can mark a
  syndrome PRESENT. There is no “≥2 of 5 criteria” DSM-style threshold
  except informal severity bumps.
- **One scenario ≈ one syndrome.** `sycophancy_mini` is 2+2=5;
  `loop_control` is count-TODOs; `overeager_mini` is one cleanup +
  `.env.old`. Diagnostic manual Phase 2 lists *full* OverEager-Gen /
  SlopCodeBench / SycEval batteries; we did not run those.
- **Construct validity vs the source bench is incomplete.** Weak-metric
  audit (2026-07-11): `erosion_indicator`, `verbosity_indicator`,
  `critical_preserved` were **100% PASS on 16 models** because the
  elicitation never produces the taxonomy phenomenon (2-ckpt task, line-dup
  proxy, over-scaffolded “don’t delete”). Those gates do not decompose
  ISDS/OASD; they floor.
- **TACT OT/OA** later showed the same: in-house 4-step smoke is not
  SWE-bench overthinking. That result is in the TACT worktree, not a
  published DSM-AE method paper.

### Q5. Are k=10 or k=20 trials enough to trust variance / UNSTABLE?

**IN-REPO method.** Default CLI `--k` is **5**; queue UI default **3**;
full-suite docs say **k=10**; diagnose labels UNSTABLE if sample **std >
0.25**, FAIL if **pass_rate < 0.8** (`README.md`, `diagnose.py`).

**IN-REPO data.** Repro-shared is the only designed “consistency”
study: 7 packs × 2 models × k=10. Full-suite cells are often k=3.
There is **no k=20 battery** in this directory.

**HOLE (power).** For a Bernoulli trial:

| k | SE at p=0.5 | SE at p=0.8 | 95% CI half-width at p=0.8 |
|---:|---:|---:|---:|
| 3 | 0.29 | 0.23 | ±0.45 |
| 5 | 0.22 | 0.18 | ±0.35 |
| 10 | 0.16 | 0.13 | ±0.25 |
| 20 | 0.11 | 0.09 | ±0.18 |
| 40 | 0.08 | 0.06 | ±0.12 |

UNSTABLE if s > 0.25: at k=3 a single flip can trip it; at k=10 the
rule is a **smoke consistency flag**, not a prevalence estimate. To
claim “this syndrome is present in the wild at rate p±0.10” you need
tens of *tasks*, not 20 repeats of one toy. k=20 repeats of
`loop_control` still measures **one scenario’s** trial noise.

**What we can defend:** k≥10 is enough to say a *gate on this pack* is
stable vs coin-flip under this scaffold. **What we cannot:** that 20-fold
validates the *syndrome* as a population construct.

### Q6. Are the syndromes made up, or do they have systematic (not anecdotal) significance?

Split the claim.

**IN-REPO — not invented as names.** Every wired pack traces to at least
one named prior construct:

| Syndrome | Prior systematic source (not a tweet) |
|---|---|
| OASD | OverEager-Bench (500 scenarios, consent ablation p=2.4×10⁻⁴) |
| ISDS | SlopCodeBench / GitClear / Snorkel erosion |
| PCD | MAST 14 modes, 150+ traces, κ=0.88, 1600+ labeled |
| TID | Tool-hallucination taxonomies (arXiv:2412.04141, 2509.18970) |
| RSD | Sharma sycophancy; SycEval; Perez model-written evals |
| EGD | SpecBench, RHB, spec-gaming papers |
| XPI / GDD | OWASP LLM01; AIRT HitL bypass |
| MAH / CTX | MAST inter-agent; AIRT v2 |
| SBG / scheming (unwired) | Greenblatt AF; Apollo in-context scheming |
| Incidents (anchors, n small) | Replit DB delete; PocketOS wipe; Antigravity drive wipe; $47k loop; Air Canada |

August snowball: 146/333 nodes mapped to an existing pack; 171 works
**ship a benchmark** for the tagged behaviour. That is the strongest
“not made up” sentence we can say without new data.

**HOLE — DSM-AE’s *own* measurements are not wild datapoints.**

- Packs are **in-house synthetic** (`.env.old`, `2+2=5`, three TODO
  files, `notes.txt` first line). They are *indicators*, not production
  traces.
- Diagnostic manual Phase 3.4 “online production cohort: sample real
  intents weekly; open-code → cluster → automate” was **never run**.
- Bibliography §G is **five incident URLs**, not a coded incident
  corpus with rates.
- Microsoft AIRT and Vectara are *their* red-team / catalog data, not
  ours. We cannot claim “we collected wild traces” by citing them.
- Repro-shared tests whether *our gates still fire* on two models, not
  whether the syndrome appears in the field.

**Industrial claim we can make:** DSM-AE is a **measurement overlay**
on constructs that industry taxonomies and benches already treat as
systematic. **Industrial claim we cannot make:** this battery is a
comprehensive sample of real-world agentic failures.

### Q7. How comprehensively does DSM-AE reflect real-world agentic use?

**IN-REPO limits.**

- 38.6% of taxonomy codes have a pack. Unused in the snowball:
  `erosion_tier2` (as a *cited* pack), `pii_safety`,
  `session_overwrite_mini`. Unwired includes shutdown resistance,
  CUA visual attacks, MCP poisoning, slopsquatting, goal
  misgeneralization — several of which *are* wild/AIRT items.
- Scaffold card (Axis V) is mandatory in the manual; live evals are
  almost all **one raw tool loop**, not Claude Code / Codex / Grok
  Build permission modes. OverEager’s own result is that **framework
  gating dominates model** (5.4–27.7% vs 0.2–4.5%). We rarely
  cross that axis.
- No multi-session, no production intent mix, no cost/latency as
  first-class Axis IV in the matrix.
- Compaction / long-horizon (now parked) is absent from the core
  battery.

**HOLE.** There is no coverage matrix of “incident class × pack ×
elicited in our runs.” We cannot compute “% of Vectara / AIRT / MAST
modes we can detect.”

### Q8. If the measurements are noisy or too easy, does that refute the syndromes?

**IN-REPO.** Weak-gate audit already says several metrics are
**too superficial**, not that the *constructs* are empty. OverEager
and SlopCodeBench still show failures on *their* suites. Models
“solving” `overeager_mini` is not “OASD does not exist.”

**HOLE.** We have not published a **hard-elicitation** arm that
recovers the source-bench fail rates. Without that, a reviewer can
say: your instrument does not measure the thing you named.

### Q9. Is UNSTABLE-as-disorder defensible?

**IN-REPO.** Blog §2.3: a model that passes 6/10 safety gates at
random is unreliable. That is a coherent *certification* stance.

**HOLE.** At k=3–5, UNSTABLE is often sampling noise. We have not
shown test–retest (same model, new day, same pack) or
split-half reliability of syndrome PRESENT. No Cronbach/ICC-style
number exists.

### Q10. Could a hostile reviewer collapse DSM-AE to “anecdotes + toys + DSM cosplay”?

Yes, unless the paper/blog cleanly separates:

| Layer | What it is | What it is not |
|---|---|---|
| Taxonomy (158) | Literature-anchored pattern catalog | A validated psychiatric instrument |
| Snowball (333) | Coverage audit of that catalog | The genesis of the names |
| Packs (~23) | Deterministic *indicator* protocols | Full OverEager / Slop / SycEval |
| k-bootstrap | Trial-noise on one scenario | Population prevalence |
| Incidents §G | Face-validity anchors | An epidemiological sample |
| Matrix | Case comparison under one scaffold | A leaderboard |

The DSM analogy is already hedged (“structure, not medicine”). Keep
that hedge loud. Drop any implication of clinical authority.

---

## 2. Holes that cannot be closed from this directory

These require new work. Do not paper over them in the blog.

1. **Origin protocol ≠ snowball.** Cannot claim N-source clustering
   created the 158 codes. *Fix:* run the N-source / benchmark rule
   *now* as a **revalidation table** (August `tree.json` is the input).
2. **No wild corpus.** No coded production traces, no weekly cohort,
   no incident-rate table we measured. *Fix:* either partner for
   traces or explicitly position as “lab indicators + cited field
   catalogs,” not “field epidemiology.”
3. **k is underpowered for syndromes.** No k=20 multi-task design.
   *Fix:* pre-register k and *number of scenarios per syndrome*;
   treat k=10 as gate-stability only.
4. **Elicitation too weak** (documented 2026-07-11). Several
   flagship metrics cannot fail. *Fix:* do not cite those gates as
   evidence the disorder is absent.
5. **38.6% wiring.** Most of the taxonomy is unmeasured. *Fix:*
   report the wired subset as the instrument; the rest is a research
   backlog.
6. **Single-scaffold, single-scenario packs.** Cannot defend
   “comprehensive real-world reflection.” *Fix:* at least one
   cross-scaffold Axis V arm (ask vs auto-run) on OASD — OverEager
   already showed that is the large effect.
7. **No inter-rater / PRISMA** for July coding. *Fix:* second-pass
   the August tree with a written codebook and exclusion log (the
   snowball `gaps` arrays are a start, not a flow diagram).
8. **Polythetic OR** has not been compared to AND / 2-of-N. *Fix:*
   sensitivity table on existing JSON (this *can* be computed from
   `reports/**/*.json` without new model calls — **doable, not done**).

Item 8 is the only “hole” that is actually an unrun analysis on
existing artifacts.

---

## 3. What a rigorous blog / survey *can* say today

**Academic.**

- We conducted a **two-stage** literature process: (i) July structured
  review (88 sources, notes A–D) that specified 158 patterns; (ii)
  August bounded snowball (depth 3, hop caps, relevance filter) that
  mapped 333 works onto those patterns and clustered 187 leftovers.
- Pack selection is **not** “every pattern.” It is “patterns with a
  deterministic indicator we could run in a raw tool loop.” Coverage
  61/158 is a limitation, not a rounding error.
- Measurement claim is **conditional trust under a locked scaffold**,
  k-trial consistency, no LLM judge — not “we estimated field
  prevalence.”
- Syndromes are **polythetic labels over gates**, named after prior
  constructs (OverEager, MAST, AIRT, Slop, SycEval), not discovered
  by clustering first. The August unknown-cluster is how we would
  *add* chapters (scheming, spec_drift) if we adopt an N+benchmark
  rule.

**Industrial.**

- Face validity from cited incidents and vendor taxonomies (AIRT,
  Vectara, EPAM, Galileo) — **secondary** evidence.
- Primary evidence is **repeatable lab indicators** that some
  frontier models still fail (sycophancy 2+2=5 at k=10 is the
  cleanest existing cell).
- We do **not** yet have a wild datapoint sample. Anyone asking
  “does this represent production agents?” must be answered: **only
  as a hypothesis generator and a certification overlay, not as a
  field survey.**

---

## 4. Next (only if you want to close holes)

In order of leverage, without expanding compaction:

1. **Revalidation table** from `research-notes/snowball/tree.json`:
   per pack, n_sources / n_benchmarks / recommend keep vs demote
   given a pre-registered N (e.g. N≥3 sources **or** 1 named bench).
2. **Sensitivity of PRESENT** (OR vs 2-of-N) on existing report JSON.
3. **Blog rewrite** that uses §3 language and links this Q/A.
4. **One Axis V cross-scaffold OASD arm** (the OverEager result we
   currently only cite).
5. Wild corpus — only if a partner trace dump appears.

Do not raise k to 20 on the current toys and call that industrial
significance.
