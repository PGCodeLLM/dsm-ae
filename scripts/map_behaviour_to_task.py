#!/usr/bin/env python3
"""Behaviour -> task-outcome mapping over real Harbor/EvalHub trajectories.

This is the empirical slice the layered-eval note calls for: an outer task
oracle (verifier reward) that is **not** a DSM-AE gate, both outcome classes
present, and off-policy instruments scored on the same trajectories.

For every instrument B we report:

    P(fail | B)      does B hurt this task family?
    P(B | fail)      when the task fails, how often is B present?
    lift             P(fail | B) / P(fail | not B)
    risk difference  P(fail | B) - P(fail | not B)
    Fisher exact p   two-sided, plus Benjamini-Hochberg q
    stratified RD    language-adjusted (Mantel-Haenszel style pooling)

The **language-stratified** estimate is the confound control: a model that is
simply weak at Go will fail Go instances at a higher base rate, which would
make any instrument correlated with Go look causal. Pooling within-language
risk differences removes that. An instrument that survives stratification is
associated with failure *given the ecosystem*, which is the agentic-deficit
reading rather than the language-competence reading.

Usage:
    python3 scripts/map_behaviour_to_task.py \
        --root evalhub-extract \
        --out reports/behaviour-task/mapping.json \
        --md reports/behaviour-task/MAPPING.md
"""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Sequence

from dsm_ae.harbor import HarborTrial, iter_runs, score_trajectory
from dsm_ae.harbor.instruments import ANCHOR, INSTRUMENTS

# --------------------------------------------------------------- statistics


def _log_factorial_table(n: int) -> list[float]:
    tab = [0.0] * (n + 1)
    for i in range(2, n + 1):
        tab[i] = tab[i - 1] + math.log(i)
    return tab


def fisher_exact_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a,b],[c,d]].

    Sums the hypergeometric probability of every table at least as extreme
    (<= observed probability) with the same margins.
    """
    n = a + b + c + d
    if n == 0:
        return 1.0
    lf = _log_factorial_table(n)
    r1, r2 = a + b, c + d
    c1, c2 = a + c, b + d

    def logp(x: int) -> float:
        # table [[x, r1-x], [c1-x, r2-c1+x]]
        y, z, w = r1 - x, c1 - x, r2 - c1 + x
        if min(x, y, z, w) < 0:
            return float("-inf")
        return (
            lf[r1] + lf[r2] + lf[c1] + lf[c2]
            - lf[n] - lf[x] - lf[y] - lf[z] - lf[w]
        )

    obs = logp(a)
    tol = 1e-9
    total = 0.0
    lo, hi = max(0, c1 - r2), min(r1, c1)
    for x in range(lo, hi + 1):
        lp = logp(x)
        if lp <= obs + tol:
            total += math.exp(lp)
    return min(1.0, total)


def benjamini_hochberg(pvals: Sequence[float]) -> list[float]:
    m = len(pvals)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank, idx in enumerate(reversed(order), start=1):
        i = m - rank
        val = pvals[idx] * m / (i + 1)
        prev = min(prev, val)
        q[idx] = min(1.0, prev)
    return q


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - half) / d), min(1.0, (c + half) / d))


# --------------------------------------------------------------- association


@dataclass
class Association:
    instrument: str
    anchor: str
    n: int
    n_present: int
    p_fail_given_b: float
    p_fail_given_not_b: float
    p_b_given_fail: float
    p_b_given_success: float
    lift: float
    risk_diff: float
    rd_ci_lo: float
    rd_ci_hi: float
    fisher_p: float
    fisher_q: float
    strat_risk_diff: float | None
    strat_strata: int
    lang_diff_risk_diff: float | None
    lang_diff_strata: int
    base_rate_fail: float
    verdict: str


def _rd_ci(a: int, b: int, c: int, d: int) -> tuple[float, float]:
    """Wald CI for the difference of two proportions."""
    n1, n2 = a + b, c + d
    if n1 == 0 or n2 == 0:
        return (0.0, 0.0)
    p1, p2 = a / n1, c / n2
    se = math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    d0 = p1 - p2
    return (d0 - 1.96 * se, d0 + 1.96 * se)


def stratified_risk_difference(
    trials: Sequence[tuple[bool, bool, str]],
    min_per_stratum: int = 20,
) -> tuple[float | None, int]:
    """Cochran-Mantel-Haenszel style pooled risk difference across strata.

    `trials` is (behaviour_present, failed, stratum). Strata with too few
    observations, or with no variation in the behaviour, are dropped.
    """
    by: dict[str, list[tuple[bool, bool]]] = defaultdict(list)
    for present, failed, stratum in trials:
        by[stratum].append((present, failed))

    num = 0.0
    den = 0.0
    used = 0
    for rows in by.values():
        n = len(rows)
        if n < min_per_stratum:
            continue
        n1 = sum(1 for p, _ in rows if p)
        n0 = n - n1
        if n1 == 0 or n0 == 0:
            continue
        f1 = sum(1 for p, f in rows if p and f)
        f0 = sum(1 for p, f in rows if not p and f)
        rd = f1 / n1 - f0 / n0
        w = n1 * n0 / n  # CMH weight
        num += w * rd
        den += w
        used += 1
    if den == 0:
        return None, 0
    return num / den, used


def difficulty_bucket(t: HarborTrial, edges: Sequence[int]) -> str:
    """Coarse difficulty proxy: trajectory length quartile.

    Longer runs mean the agent kept working, which tracks how hard the
    instance was. This is a proxy, not a difficulty label: it is endogenous
    (a thrashing agent also produces a long trace), so it is reported as a
    second stratification arm rather than as the headline estimate.
    """
    n = len(t.tool_calls)
    for i, e in enumerate(edges):
        if n <= e:
            return f"q{i + 1}"
    return f"q{len(edges) + 1}"


def _quartile_edges(trials: Sequence[HarborTrial]) -> list[int]:
    lens = sorted(len(t.tool_calls) for t in trials)
    if not lens:
        return [0, 0, 0]
    return [lens[int(len(lens) * f)] for f in (0.25, 0.5, 0.75)]


def associate(
    trials: Sequence[HarborTrial],
    scores: Sequence[dict[str, bool]],
    *,
    stratify_by: str = "language",
) -> list[Association]:
    labelled = [
        (t, s) for t, s in zip(trials, scores) if t.success is not None
    ]
    n_total = len(labelled)
    if n_total == 0:
        return []
    base_fail = sum(1 for t, _ in labelled if not t.success) / n_total
    edges = _quartile_edges([t for t, _ in labelled])

    raw: list[Association] = []
    for ins in INSTRUMENTS:
        a = b = c = d = 0  # a: B&fail, b: B&success, c: !B&fail, d: !B&success
        strat_rows: list[tuple[bool, bool, str]] = []
        joint_rows: list[tuple[bool, bool, str]] = []
        for t, s in labelled:
            present = s[ins.key]
            failed = not t.success
            lang = getattr(t, stratify_by, "unknown")
            strat_rows.append((present, failed, lang))
            joint_rows.append(
                (present, failed, f"{lang}|{difficulty_bucket(t, edges)}")
            )
            if present and failed:
                a += 1
            elif present and not failed:
                b += 1
            elif not present and failed:
                c += 1
            else:
                d += 1

        n_present = a + b
        n_absent = c + d
        n_fail = a + c
        n_succ = b + d

        p_fail_b = a / n_present if n_present else 0.0
        p_fail_nb = c / n_absent if n_absent else 0.0
        lift = (p_fail_b / p_fail_nb) if p_fail_nb > 0 else float("inf") if p_fail_b else 1.0
        rd = p_fail_b - p_fail_nb
        lo, hi = _rd_ci(a, b, c, d)
        p = fisher_exact_two_sided(a, b, c, d)
        srd, nstrata = stratified_risk_difference(strat_rows)
        jrd, njstrata = stratified_risk_difference(joint_rows, min_per_stratum=15)

        raw.append(
            Association(
                instrument=ins.key,
                anchor=ins.anchor,
                n=n_total,
                n_present=n_present,
                p_fail_given_b=p_fail_b,
                p_fail_given_not_b=p_fail_nb,
                p_b_given_fail=(a / n_fail if n_fail else 0.0),
                p_b_given_success=(b / n_succ if n_succ else 0.0),
                lift=lift,
                risk_diff=rd,
                rd_ci_lo=lo,
                rd_ci_hi=hi,
                fisher_p=p,
                fisher_q=1.0,
                strat_risk_diff=srd,
                strat_strata=nstrata,
                lang_diff_risk_diff=jrd,
                lang_diff_strata=njstrata,
                base_rate_fail=base_fail,
                verdict="",
            )
        )

    qs = benjamini_hochberg([r.fisher_p for r in raw])
    for r, q in zip(raw, qs):
        r.fisher_q = q
        r.verdict = _verdict(r)
    raw.sort(key=lambda r: (-abs(r.risk_diff), r.fisher_q))
    return raw


def _verdict(r: Association) -> str:
    """Plain-language read of one association, confound-aware."""
    if r.n_present < 15:
        return "underpowered"
    if r.fisher_q >= 0.05:
        return "not significant"
    crosses_zero = r.rd_ci_lo <= 0 <= r.rd_ci_hi
    if crosses_zero:
        return "not significant"
    # Does the effect survive language stratification?
    if r.strat_risk_diff is not None and r.strat_strata >= 2:
        if r.risk_diff > 0 and r.strat_risk_diff < 0.5 * r.risk_diff:
            return "confounded by language"
        if r.risk_diff < 0 and r.strat_risk_diff > 0.5 * r.risk_diff:
            return "confounded by language"
    # And language x difficulty jointly? Difficulty is endogenous (a thrashing
    # agent also produces a long trace), so collapse here is reported as
    # "difficulty-entangled" rather than as a clean refutation.
    if r.lang_diff_risk_diff is not None and r.lang_diff_strata >= 3:
        if r.risk_diff > 0 and r.lang_diff_risk_diff < 0.5 * r.risk_diff:
            return "difficulty-entangled"
        if r.risk_diff < 0 and r.lang_diff_risk_diff > 0.5 * r.risk_diff:
            return "difficulty-entangled"
    if r.p_b_given_fail < 0.05:
        return "significant but rare"
    return "predicts failure" if r.risk_diff > 0 else "predicts success"


# --------------------------------------------------------------- reporting


def _fmt_pct(x: float) -> str:
    return f"{x:.1%}"


def render_markdown(
    blocks: list[tuple[str, int, int, list[Association]]],
    lang_table: dict[str, dict[str, Counter]],
    excluded: Counter | None = None,
) -> str:
    out: list[str] = []
    out.append("# Behaviour → task-outcome mapping\n")
    out.append(
        "Off-policy DSM-AE instruments scored against real agentic task\n"
        "trajectories whose success oracle is the benchmark verifier, not a\n"
        "DSM-AE gate. This is the third layer of the metric → behaviour → task\n"
        "stack: it answers *which behaviours are load-bearing for which jobs*.\n"
    )
    out.append(
        "\n**Reading the table.** `P(fail|B)` is the failure rate among runs where\n"
        "the behaviour fired; `P(B|fail)` is how often failures carry it. `RD` is\n"
        "the risk difference with a 95% Wald interval, `q` is the\n"
        "Benjamini-Hochberg adjusted Fisher p.\n"
        "\n`RD*` is the **language-stratified** risk difference (CMH-pooled within\n"
        "ecosystem). An instrument whose plain RD is large but whose RD* collapses\n"
        "is tracking the ecosystem — the model is weak at Go — not an agentic\n"
        "deficit.\n"
        "\n`RD**` additionally stratifies on a **difficulty proxy** (trajectory-length\n"
        "quartile within language). Treat this column as a stress test, not as the\n"
        "headline: trace length is endogenous, since a thrashing agent produces a\n"
        "long trace for reasons that are themselves the behaviour under study.\n"
        "Conditioning on it can absorb genuine signal, so a shrunken `RD**` is\n"
        "flagged `difficulty-entangled` rather than treated as a refutation.\n"
    )

    for title, n_pass, n_fail, assocs in blocks:
        out.append(f"\n## {title}\n")
        out.append(f"n = {n_pass + n_fail} ({n_pass} pass / {n_fail} fail)\n")
        if not assocs:
            out.append("\n_No labelled trials._\n")
            continue
        out.append(
            "\n| Instrument | Anchor | n(B) | P(fail\\|B) | P(fail\\|¬B) | P(B\\|fail) "
            "| RD [95% CI] | RD* lang | RD** lang×diff | q | Verdict |\n"
            "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---|\n"
        )
        for r in assocs:
            srd = "—" if r.strat_risk_diff is None else f"{r.strat_risk_diff:+.3f}"
            jrd = (
                "—"
                if r.lang_diff_risk_diff is None
                else f"{r.lang_diff_risk_diff:+.3f}"
            )
            out.append(
                f"| `{r.instrument}` | {r.anchor} | {r.n_present} "
                f"| {_fmt_pct(r.p_fail_given_b)} | {_fmt_pct(r.p_fail_given_not_b)} "
                f"| {_fmt_pct(r.p_b_given_fail)} "
                f"| {r.risk_diff:+.3f} [{r.rd_ci_lo:+.3f}, {r.rd_ci_hi:+.3f}] "
                f"| {srd} | {jrd} | {r.fisher_q:.3g} | {r.verdict} |\n"
            )

    if excluded:
        total_ex = sum(excluded.values())
        out.append("\n## Excluded: trials whose reward did not measure the model\n")
        out.append(
            f"\n{total_ex} trials carried a reward that is not a measurement of\n"
            "model behaviour, for one of two **structural** reasons:\n"
            "\n1. **Zero tests ran** — an empty `tests` list in\n"
            "   `verifier/output.json`: scored 0 without a single test executing.\n"
            "2. **The harness failed** — `result.json.exception_info` records a\n"
            "   trial-level failure (network, agent timeout, non-zero agent exit,\n"
            "   API/auth error). These are invisible in `trial.log`, which is why\n"
            "   an earlier pass reported \"zero errors\" while 119 reference trials\n"
            "   carried one.\n"
            "\nBoth mean the record shows the measurement *could not have happened*.\n"
            "A reward that merely disagrees with a partial success signal is **not**\n"
            "excluded — that case was adjudicated and rejected (defense Q/A Q18).\n"
            "\nThis matters because neither artifact is evenly distributed. Left in,\n"
            "they inflate the failure rate of whichever ecosystem they hit and\n"
            "manufacture precisely the language-deficit conclusion this study exists\n"
            "to rule out.\n"
        )
        out.append("\n| Language — reason | excluded |\n|---|---:|\n")
        for lang, n in sorted(excluded.items(), key=lambda kv: -kv[1]):
            out.append(f"| {lang} | {n} |\n")

    out.append("\n## Language base rates (the confound)\n")
    out.append(
        "\nIf failure rate varies sharply by ecosystem, any instrument correlated\n"
        "with ecosystem inherits that signal. These are the base rates the `RD*`\n"
        "column adjusts for.\n"
    )
    for run, langs in lang_table.items():
        out.append(f"\n**{run}**\n\n| Language | n | fail rate |\n|---|---:|---:|\n")
        for lang, c in sorted(langs.items(), key=lambda kv: -sum(kv[1].values())):
            n = c["pass"] + c["fail"]
            if not n:
                continue
            out.append(f"| {lang} | {n} | {c['fail'] / n:.1%} |\n")

    out.append("\n## What this does and does not establish\n")
    out.append(
        "\n- The oracle is external (verifier reward), so the association is not\n"
        "  circular with any DSM-AE gate.\n"
        "- Association is not causation. A surviving `RD*` means the behaviour\n"
        "  predicts failure *within* an ecosystem; it does not prove the\n"
        "  behaviour caused it. Difficulty is not matched.\n"
        "- Instruments are off-policy analogues of pack gates, not the gates\n"
        "  themselves. `edited_test_files` in particular has a high base rate on\n"
        "  SWE-bench-Pro, where touching tests is often legitimate.\n"
        "- Scaffold is fixed per run (Axis V). Cross-scaffold claims are not\n"
        "  supported by this table.\n"
    )
    return "".join(out)


# --------------------------------------------------------------- main


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path("evalhub-extract"))
    ap.add_argument("--out", type=Path, default=Path("reports/behaviour-task/mapping.json"))
    ap.add_argument("--md", type=Path, default=Path("reports/behaviour-task/MAPPING.md"))
    ap.add_argument("--min-trials", type=int, default=40)
    args = ap.parse_args(argv)

    by_source: dict[str, list[HarborTrial]] = defaultdict(list)
    lang_table: dict[str, dict[str, Counter]] = {}
    excluded: Counter = Counter()

    for run_name, trials in iter_runs(args.root):
        if not trials:
            continue
        langs: dict[str, Counter] = defaultdict(Counter)
        for t in trials:
            if t.reward is not None and not t.scoreable:
                reason = (
                    "zero tests ran"
                    if t.n_tests_run == 0
                    else f"harness: {t.exception_type}"
                )
                excluded[f"{t.language} — {reason}"] += 1
            if t.success is None:
                continue
            langs[t.language]["pass" if t.success else "fail"] += 1
        lang_table[run_name] = dict(langs)
        for t in trials:
            by_source[t.source].append(t)
        n_ex = sum(1 for t in trials if t.reward is not None and not t.scoreable)
        print(f"loaded {run_name}: {len(trials)} trials ({n_ex} unscoreable)")

    if excluded:
        print("excluded (reward did not measure the model):")
        for k, v in sorted(excluded.items(), key=lambda kv: -kv[1]):
            print(f"   {v:5d}  {k}")

    blocks: list[tuple[str, int, int, list[Association]]] = []
    payload: dict[str, object] = {"sources": {}}

    for source, trials in sorted(by_source.items()):
        labelled = [t for t in trials if t.success is not None]
        if len(labelled) < args.min_trials:
            print(f"skip {source}: only {len(labelled)} labelled trials")
            continue
        scores = [score_trajectory(t) for t in labelled]
        assocs = associate(labelled, scores)
        n_pass = sum(1 for t in labelled if t.success)
        n_fail = len(labelled) - n_pass
        blocks.append((source, n_pass, n_fail, assocs))
        payload["sources"][source] = {  # type: ignore[index]
            "n_pass": n_pass,
            "n_fail": n_fail,
            "associations": [asdict(a) for a in assocs],
        }

    payload["language_base_rates"] = {
        run: {lang: dict(c) for lang, c in langs.items()}
        for run, langs in lang_table.items()
    }
    payload["excluded_zero_test_trials"] = dict(excluded)
    payload["instruments"] = {
        ins.key: {"anchor": ins.anchor, "det": ins.det, "doc": ins.doc}
        for ins in INSTRUMENTS
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2))
    args.md.parent.mkdir(parents=True, exist_ok=True)
    args.md.write_text(render_markdown(blocks, lang_table, excluded))
    print(f"wrote {args.out} and {args.md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
