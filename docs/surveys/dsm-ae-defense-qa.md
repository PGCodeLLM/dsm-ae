# DSM-AE academic + industrial defense — adversarial Q/A

**AS_OF:** 2026-09-04  
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

**IN-REPO data.** Repro-shared is the designed “consistency” study
(pack folders × models × k=10). Full-suite cells are often k=3. A
gpt-5.6-*(max) k=20 expansion is in flight; it is not required to
read the floor below.

**IN-REPO — procedure noise floor (2026-09-04).** Same-condition
split JSD on atom n-gram fingerprints (`src/dsm_ae/atoms.py`,
`reports/trajectory-atoms/ANALYSIS.md`), 3380 labeled trials, vocab
spec `58a2e58fb494:3`:

| split n | # model×pack | mean floor | median p97.5 |
|---:|---:|---:|---:|
| 5 | 271 | 0.06 | 0.09 |
| 10 | 17 | 0.06 | (max 0.11) |

This floor is **much lower** than procgrep’s SWE-agent numbers
(~0.56 at n=5) because our traces are short (median 9 tool calls)
and low-diversity. 271 conditions: **147/271 (54%)** can resolve a
procedure shift of Δ=0.10; **212/271 (78%)** can resolve Δ=0.20.
So k=5 is often enough to detect a *large* how-they-work change on
these toys, and k=10 rarely buys another decimal.

Pass vs fail JSD is **above** that floor for process-shaped packs
(`tool_integrity_tier2` 0.35, `handoff_mini` 0.26, `coord_tax_mini`
0.24, `mas_verify_mini` 0.26) and **at/below** it for
target-shaped packs (`overeager_mini` 0.04, `recency_bias_mini`
0.05): those fails are the same program hitting the wrong file/doc,
not a different action sequence. AUC can look high on n_fail=3–8
packs (`loop_control`, `slop_indicator`) — treat those as
overfit.

**HOLE (power).** For a Bernoulli *gate* (not a procedure JSD):

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
stable vs coin-flip under this scaffold. On *procedure* JSD, k=5
already sits on a ~0.09 noise floor for these short traces; k=20
will not turn overeager/recency into a process discriminator.
**What we cannot:** that 20-fold validates the *syndrome* as a
population construct, or that a high AUC on n_fail&lt;10 is a
stable pattern.

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

### Q11. What does DSM-AE offer that MCTS automated benches (PrismBench, ProbeLLM) do not?

This is the industrial-value question. Answer it as a **level-of-analysis**
difference, not as “we search better” or “we have more items.”

**What those methods actually do (do not strawman).**

| Method | Unit of evaluation | Search / aggregation | Decision you can take |
|---|---|---|---|
| **PrismBench** (Majdinasab, Nikanjam, Khomh, TMLR 2026; [OpenReview](https://openreview.net/forum?id=O0bsC6FDly); arXiv:2504.05500) | Generated *LeetCode-style* coding challenges (spec → tests → solution → repair). State = concept × difficulty. | MDP + MCTS to find *high-failure* regions of that challenge tree. Metrics: success@k, failure rate by concept/difficulty. | “This model is weak on DP / conditionals at this generated difficulty.” |
| **ProbeLLM** (Huang et al., ICML 2026; arXiv:2602.12966) | A prompt with a *verifiable ground-truth answer*. Seeds: MMLU, SuperGLUE, MBPP, HellaSwag, TruthfulQA. Failure = verifier rejects `y` vs `y*`. | Hierarchical MCTS (Macro coverage / Micro perturbation) → cluster failures into *failure modes*. | “This model has a recurring QA/knowledge/codegen-item error cluster” (their example lineage includes domain trivia such as EPR hyperfine splitting). |

Both are good at **discovering hard items** and **naming recurring error
patterns in a Question/Answer (or puzzle-codegen) frame**. PrismBench
explicitly cites SWE-bench as a static bench that saturates, then
*replaces* it with a harder generated LC-style tree — still “can the
model solve this isolated programming challenge,” not “is this agent
fit to operate in a repo.” ProbeLLM *restricts* to well-defined
ground-truth answers and reports error rate / cluster novelty. Neither
asks whether the failure **matters at the level of an agentic job**.

**IN-REPO — what DSM-AE is built to answer instead.**

The diagnostic object is a **locked-scaffold agentic trial**: tools,
workspace, permission mode, multi-turn trace, deterministic gates on
*what the agent did* (`src/dsm_ae/criteria.py`,
`docs/appendices/METRIC_ALGORITHMS.md`). Syndromes are **operational
fitness labels**, not item-error clusters:

| If PRESENT | Industrial question it is trying to answer |
|---|---|
| OASD | Will it take unauthorized side effects (delete, overwrite, “cleanup”) when the job did not ask? |
| TID | Will it invent tool results / file contents and proceed? |
| PCD | Will it loop / fail to stop when the workspace is already done? |
| RSD | Will it agree with a false user claim under social pressure? |
| GDD / XPI | Will it skip a required gate or follow injected untrusted content? |
| MAH / CSO / CTX | Can it hand off or keep session state without clobbering a peer? |
| UNSTABLE (std>0.25) | Even if the mean is fine, is it too noisy to certify? |

That is closer to **fitness-to-operate** (may this model be put on
code-review / cleanup / pairing the way a human is licensed to drive)
than to **hardest-item discovery**. A model can ace generated DP
puzzles and still be unfit to review a PR if it “helpfully” deletes
`.env.old`, hallucinates a `git` result, or folds on `2+2=5`.
Conversely, failing an MCTS-mined EPR-spectroscopy item has **no
implied blast radius** for a software-engineering deployment.

Three properties MCTS-QA/codegen search does not give you, that the
framework is designed to give:

1. **Task-level, not item-level.** The atomic record is a multi-turn
   tool loop against a workspace, not `(x, y, y*)`. Gates read
   `files_deleted`, re-reads, unauthorized writes, injected-content
   compliance — things that only exist in an *agent* trace.
2. **Consequence-shaped labels.** OASD/TID/GDD name *how the job
   fails operationally* (unauthorized action, ungrounded tool use,
   skipped gate). ProbeLLM modes name *how the answer is wrong*.
   PrismBench names *which programming concept × difficulty is hard*.
   An org can map the former onto a hire / auto-run / require-HITL
   policy; they cannot map “weak on generated DP” onto “safe to
   auto-merge code review.”
3. **Certification stance, not a moving leaderboard.** PASS / FAIL /
   UNSTABLE under a declared scaffold card (blog §2.3, Q9). MCTS
   benches are *adversarial search*: they keep generating harder
   items until the score drops. That is useful for capability
   frontiers. It is the wrong object for “is this agent reliable
   enough to operate this class of task.” Reliability is
   **stability on the job you will actually assign**, not
   **performance at the hardest item a searcher can invent**.

**HOLE — do not over-claim the current battery as that industrial
exam.**

- Packs are still **one-scenario toys** (`.env.old`, three TODOs,
  `2+2=5`). They are the *closed-course / indicator* analog of a
  driving test, not an on-road code-review cohort. Diagnostic
  manual Phase 3.4 (production intents) was never run (Q6–Q7).
- We have **no pack that is “review this real PR.”** Code-review
  fitness is the *target industrial use*, not a completed
  measurement. Claiming “DSM-AE already certifies code-review
  fitness” is false.
- Raising k to 20 on the same toys (in progress for
  `gpt-5.6-{sol,terra,luna}(max)`) tightens **trial-noise CIs on
  those indicators** (Q5). It does **not** by itself create
  industrial significance. Do not cite k=20 as the answer to this
  Q.
- Axis V (ask vs auto-run / Claude Code vs raw loop) is almost
  unused; OverEager already showed *framework gating* dominates
  model. A fitness exam that only tests one scaffold is like a
  driving test on one parking lot.

**Honest defense sentence for the blog / industrial pitch:**

> MCTS automated benches (PrismBench, ProbeLLM) are strong at
> *finding* Q/A and puzzle-codegen failures. They do not say
> whether those failures have blast radius on an agentic software
> job. DSM-AE’s distinctive offer is a **fitness-to-operate
> overlay**: syndrome labels over deterministic agent traces,
> aimed at decisions like “may this model auto-run code review /
> cleanup / pairing.” Today that overlay is a **seed indicator
> battery** on synthetic SE-agent scenarios, not a production
> medical or licensing instrument. The gap we cover — and still
> owe harder packs for — is *task-level operational fitness*,
> not *harder items*.

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
9. **Fitness-to-operate is the offer, not the delivered product.**
   Q11 is a *level-of-analysis* claim. We do not yet have a
   code-review / on-call pack with real blast-radius oracles. *Fix:*
   one industrial job pack (e.g. review a fixture PR that contains a
   secret + an unauthorized cleanup lure) before using the driving-
   license analogy in a paper abstract.

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
- Versus MCTS automated benches (PrismBench, ProbeLLM): they
  discover hard *items*; we score *agent traces* for operational
  syndromes. That is the industrial differentiator (fitness to
  perform an SE job, not a harder Q/A cluster). It is **not**
  yet a completed code-review licensing exam — see Q11.

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
