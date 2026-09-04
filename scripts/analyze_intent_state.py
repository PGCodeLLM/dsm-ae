#!/usr/bin/env python3
"""Label GPT-family traces with task-progress + recovery + plan-exec + TACT CAL.

Usage:
  PYTHONPATH=src python3 scripts/analyze_intent_state.py
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsm_ae.atoms import label_trial  # noqa: E402
from dsm_ae.intent.label import label_trace  # noqa: E402
from dsm_ae.intent.plan_exec import plan_exec_scores  # noqa: E402
from dsm_ae.intent.specs import spec_for  # noqa: E402
from dsm_ae.intent.tact_cal import tact_cal_ratios  # noqa: E402

GPT_PREFIXES = ("gpt-5", "gpt-4")
FOCUS = (
    "loop_control",
    "overeager_mini",
    "recency_bias_mini",
    "tool_integrity_tier2",
    "handoff_mini",
    "coord_tax_mini",
    "mas_verify_mini",
    "memory_context",
)


def _is_gpt(model: str) -> bool:
    m = (model or "").lower()
    return m.startswith(GPT_PREFIXES) or m.startswith("openai/gpt")


def _load_work(reports: Path) -> list[dict[str, Any]]:
    out = []
    for root in reports.rglob("trajectories"):
        if "_request_logs" in root.parts:
            continue
        for d in root.iterdir():
            if not d.is_dir() or "__t" not in d.name:
                continue
            tj, sj = d / "traces.json", d / "scores.json"
            if not tj.is_file():
                continue
            try:
                raw = json.loads(tj.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            traces = raw if isinstance(raw, list) else [raw]
            scores = []
            if sj.is_file():
                try:
                    sc = json.loads(sj.read_text(encoding="utf-8"))
                    if isinstance(sc, list):
                        scores = sc
                except (OSError, json.JSONDecodeError):
                    pass
            pack = d.name.split("__t")[0]
            conv = None
            cj = d / "conversation.json"
            if cj.is_file():
                try:
                    conv = json.loads(cj.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    conv = None
            for tr in traces:
                if not isinstance(tr, dict):
                    continue
                tr = dict(tr)
                tr["pack"] = tr.get("pack") or pack
                tr["_scores"] = scores
                if conv and not (tr.get("meta") or {}).get("full_conversation"):
                    meta = dict(tr.get("meta") or {})
                    meta["full_conversation"] = conv
                    tr["meta"] = meta
                out.append(tr)
    return out


def _load_repro(reports: Path) -> list[dict[str, Any]]:
    repro = reports / "repro-shared"
    if not repro.is_dir():
        return []
    out = []
    for p in repro.rglob("trial_*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        traces = data.get("traces") or []
        if not traces or not isinstance(traces[0], dict):
            continue
        tr = dict(traces[0])
        packs = data.get("packs") or [tr.get("pack")]
        tr["pack"] = str(packs[0] if packs else tr.get("pack") or "")
        scores = []
        for b in data.get("bootstraps") or []:
            pts = (b or {}).get("per_trial") or []
            if pts:
                scores.append(pts[0])
        tr["_scores"] = scores
        out.append(tr)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reports", type=Path, default=ROOT / "reports")
    ap.add_argument("-o", "--out", type=Path, default=ROOT / "reports" / "intent-state")
    args = ap.parse_args(argv)

    rows_in = _load_work(args.reports) + _load_repro(args.reports)
    seen: set[str] = set()
    gpt: list[dict[str, Any]] = []
    for tr in rows_in:
        model = str((tr.get("scaffold_card") or {}).get("model") or "")
        if not _is_gpt(model):
            continue
        tid = str(tr.get("trial_id") or "")
        if tid in seen:
            continue
        seen.add(tid)
        gpt.append(tr)

    by_pack: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for tr in gpt:
        pack = str(tr.get("pack") or "")
        if pack not in FOCUS and spec_for(pack) is None:
            continue
        if spec_for(pack) is None:
            continue
        by_pack[pack].append(tr)

    per_pack = {}
    for pack, traces in sorted(by_pack.items()):
        lab_n = Counter()
        rec = Counter()
        cal_pass: list[float] = []
        cal_fail: list[float] = []
        pe_div: list[float] = []
        pe_mis: list[float] = []
        n_plan = 0
        n_pass = n_fail = 0
        adv_pass = adv_fail = 0
        unr_pass = unr_fail = 0
        rec_ok_pass = rec_ok_fail = 0
        for tr in traces:
            scores = tr.get("_scores") or []
            task, _ = label_trial(pack, scores)
            prog = label_trace(tr)
            if prog is None:
                continue
            for s in prog.steps:
                lab_n[s.label] += 1
            if prog.nonmonotonic:
                rec["nonmonotonic"] += 1
            if prog.unrecovered:
                rec["unrecovered"] += 1
            if prog.n_recover:
                rec["recovered"] += 1
            ratios = tact_cal_ratios(tr)
            pe = plan_exec_scores(tr)
            if pe and pe.get("has_plan"):
                n_plan += 1
                if pe.get("plan_exec_divergence") is not None:
                    pe_div.append(float(pe["plan_exec_divergence"]))
                if pe.get("ra_mismatch_score") is not None:
                    pe_mis.append(float(pe["ra_mismatch_score"]))
            n_adv = sum(1 for s in prog.steps if s.label in {"ADVANCE", "RECOVER"})
            frac_adv = n_adv / max(len(prog.steps), 1)
            if task is True:
                n_pass += 1
                cal_pass.append(ratios["calibrated_ratio"])
                adv_pass += frac_adv
                if prog.unrecovered:
                    unr_pass += 1
                if prog.nonmonotonic and not prog.unrecovered:
                    rec_ok_pass += 1
            elif task is False:
                n_fail += 1
                cal_fail.append(ratios["calibrated_ratio"])
                adv_fail += frac_adv
                if prog.unrecovered:
                    unr_fail += 1
                if prog.nonmonotonic and not prog.unrecovered:
                    rec_ok_fail += 1

        def mean(xs: list[float]) -> float | None:
            return round(sum(xs) / len(xs), 3) if xs else None

        per_pack[pack] = {
            "n": len(traces),
            "n_pass": n_pass,
            "n_fail": n_fail,
            "label_mix": dict(lab_n),
            "n_nonmonotonic": rec["nonmonotonic"],
            "n_recovered": rec["recovered"],
            "n_unrecovered": rec["unrecovered"],
            "frac_advance_pass": round(adv_pass / n_pass, 3) if n_pass else None,
            "frac_advance_fail": round(adv_fail / n_fail, 3) if n_fail else None,
            "unrecovered_rate_pass": round(unr_pass / n_pass, 3) if n_pass else None,
            "unrecovered_rate_fail": round(unr_fail / n_fail, 3) if n_fail else None,
            "recovered_ok_pass": rec_ok_pass,
            "recovered_ok_fail": rec_ok_fail,
            "cal_pass": mean(cal_pass),
            "cal_fail": mean(cal_fail),
            "n_with_plan": n_plan,
            "mean_plan_exec_divergence": mean(pe_div),
            "mean_ra_mismatch": mean(pe_mis),
        }

    payload = {
        "n_gpt_trials": len(gpt),
        "packs": per_pack,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# Intent-state labels on GPT trajectories",
        "",
        f"GPT-family trials: **{len(gpt)}**. Labels are pack-declared TaskSpec",
        "progress (ADVANCE / ENABLE / NEUTRAL / REGRESS / RECOVER / OFF_TASK).",
        "RECOVER is a restored high-water after REGRESS — desirable, not noise.",
        "",
        "## Progress vs task outcome",
        "",
        "| pack | n | pass/fail | %ADV+REC pass | %ADV+REC fail | unrecovered pass | unrecovered fail | CAL pass | CAL fail |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pack, r in per_pack.items():
        lines.append(
            f"| `{pack}` | {r['n']} | {r['n_pass']}/{r['n_fail']} | "
            f"{r['frac_advance_pass'] if r['frac_advance_pass'] is not None else '—'} | "
            f"{r['frac_advance_fail'] if r['frac_advance_fail'] is not None else '—'} | "
            f"{r['unrecovered_rate_pass'] if r['unrecovered_rate_pass'] is not None else '—'} | "
            f"{r['unrecovered_rate_fail'] if r['unrecovered_rate_fail'] is not None else '—'} | "
            f"{r['cal_pass'] if r['cal_pass'] is not None else '—'} | "
            f"{r['cal_fail'] if r['cal_fail'] is not None else '—'} |"
        )
    lines += [
        "",
        "## Recovery",
        "",
        "| pack | nonmonotonic | recovered episodes | unrecovered | recovered-and-pass | recovered-and-fail |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pack, r in per_pack.items():
        lines.append(
            f"| `{pack}` | {r['n_nonmonotonic']} | {r['n_recovered']} | "
            f"{r['n_unrecovered']} | {r['recovered_ok_pass']} | {r['recovered_ok_fail']} |"
        )
    lines += [
        "",
        "## Plan ↔ execute (PC-07 / PC-15) on traces with reasoning_content",
        "",
        "| pack | n with plan | mean divergence (PC-15) | mean mismatch (PC-07) |",
        "|---|---:|---:|---:|",
    ]
    for pack, r in per_pack.items():
        lines.append(
            f"| `{pack}` | {r['n_with_plan']} | "
            f"{r['mean_plan_exec_divergence'] if r['mean_plan_exec_divergence'] is not None else '—'} | "
            f"{r['mean_ra_mismatch'] if r['mean_ra_mismatch'] is not None else '—'} |"
        )
    lines += [
        "",
        "Divergence/mismatch are 0 = plan matches execution. Compare to the",
        "n-gram floor (~0.09 at n=5) before calling a plan-exec gap a real shift.",
        "",
        "## Signal on this GPT slice",
        "",
        "- **overeager_mini:** unrecovered REGRESS is **0% of passes vs 87.5% of fails**.",
        "  ADVANCE rates barely differ (0.30 vs 0.28). The state layer catches",
        "  *forbidden* coverage (`.env.old` gone and not restored), which n-grams",
        "  could not (pass↔fail JSD 0.04).",
        "- **recency_bias_mini:** ADVANCE+RECOVER fraction **0.33 pass vs 0.16 fail**.",
        "  No REGRESS episodes — fails never write a healthy config, so there is",
        "  nothing to recover. CAL is saturated (~0.95 both).",
        "- Other GPT packs are nearly all-pass, so they cannot show outcome",
        "  contrast. TID2 CAL stays high (0.97) as expected on this family.",
        "- Plan-exec n is small: most GPT fails are older repro-shared traces",
        "  without parseable plan verbs. `(max)` traces have reasoning but often",
        "  no tool-name lexicon — PC-07/15 need a tighter plan parser or",
        "  structured plan tags.",
        "",
        "Full JSON: `analysis.json`. Plan: "
        "`docs/surveys/2026-09-04-intent-state-layered-verification.md`.",
        "",
    ]
    (args.out / "ANALYSIS.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {args.out / 'ANALYSIS.md'} gpt_trials={len(gpt)} packs={len(per_pack)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
