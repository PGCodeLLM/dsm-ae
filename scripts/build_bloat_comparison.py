#!/usr/bin/env python3
"""Build Comparison tab: baseline vs context-bloat 50% (side-by-side metrics).

Writes:
  reports/bloat/bloat50/comparison.html
  reports/bloat/bloat50/{model}.json  (assembled from scores.json / checkpoints)

Default models: those with checkpoints under reports/bloat/bloat50/work/.
Default packs: only packs with full k checkpoints (excludes incomplete
tool_integrity_tier2 until it finishes).
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from dsm_ae.criteria import evaluate_findings  # noqa: E402
from dsm_ae.metrics.bootstrap import bootstrap_metric, build_gate_matrix  # noqa: E402
from dsm_ae.models import MetricResult  # noqa: E402
from dsm_ae.packs.registry import list_packs  # noqa: E402
from dsm_ae.report import render_markdown  # noqa: E402
from json_to_html_report import (  # noqa: E402
    build_html,
    discover_jsons,
    load_report,
    merge_reports,
    model_id,
)


def _ckpt_count(work: Path, pack: str, k: int) -> int:
    ck = work / ".dsm_ae_ckpt"
    if not ck.is_dir():
        return 0
    return sum(1 for t in range(k) if (ck / f"{pack}__t{t}.json").is_file())


def packs_complete_for_model(work: Path, packs: list[str], k: int) -> list[str]:
    return [p for p in packs if _ckpt_count(work, p, k) >= k]


def _load_scores_for_trial(work: Path, pack: str, trial: int) -> list[MetricResult]:
    """Load MetricResults from scores.json or lightweight checkpoint items."""
    scores_path = work / "trajectories" / f"{pack}__t{trial}" / "scores.json"
    if scores_path.is_file():
        try:
            raw = json.loads(scores_path.read_text(encoding="utf-8"))
            if isinstance(raw, list) and raw:
                return [MetricResult.model_validate(m) for m in raw]
        except Exception:
            pass
    # Fallback: checkpoint items (skip heavy Trace validation when possible)
    ck = work / ".dsm_ae_ckpt" / f"{pack}__t{trial}.json"
    if not ck.is_file():
        return []
    try:
        raw = json.loads(ck.read_text(encoding="utf-8"))
        items = raw.get("items") or []
        out: list[MetricResult] = []
        for it in items:
            for m in it.get("scores") or []:
                out.append(MetricResult.model_validate(m))
        return out
    except Exception:
        return []


def assemble_bloat_report(
    *,
    model: str,
    work: Path,
    packs: list[str],
    k: int,
    level: float,
) -> dict[str, Any] | None:
    """Assemble a DiagnosisReport-shaped dict from existing trial scores."""
    if not packs:
        return None
    bucket: dict[str, list[MetricResult]] = {}
    loaded = 0
    for pack in packs:
        for t in range(k):
            scores = _load_scores_for_trial(work, pack, t)
            if not scores:
                continue
            loaded += 1
            for m in scores:
                bucket.setdefault(m.metric_id, []).append(m)
    if not bucket:
        return None

    boots = [
        bootstrap_metric(
            mid,
            mid,
            results,
            threshold_pass=0.8,
            threshold_std=0.25,
        )
        for mid, results in bucket.items()
    ]
    boots.sort(key=lambda b: b.metric_id)
    gates = build_gate_matrix(boots)
    findings = evaluate_findings(boots)

    report = {
        "run_id": str(uuid.uuid4()),
        "scaffold_card": {
            "model": model,
            "scaffold": "raw",
            "permission_mode": "default",
            "k_trials": k,
            "max_turns": 10,
            "extra": {
                "context_bloat": {
                    "level": level,
                    "model": model,
                    "token_method": "char4",
                    "seed": 42,
                    "overflow_is_fail": True,
                },
                "assembled_from_scores": True,
            },
        },
        "packs": list(packs),
        "k_trials": k,
        "gates": [g.model_dump(mode="json") for g in gates],
        "findings": [f.model_dump(mode="json") for f in findings],
        "bootstraps": [b.model_dump(mode="json") for b in boots],
        "traces": [],
        "notes": [
            f"Assembled from scores under {work} (no re-LLM).",
            f"Packs ({len(packs)}): {', '.join(packs)}",
            f"Trials loaded: {loaded}/{len(packs) * k}",
            f"Context bloat level={level}",
        ],
    }
    return report


def _relabel(rep: dict[str, Any], label: str) -> dict[str, Any]:
    out = dict(rep)
    card = dict(out.get("scaffold_card") or {})
    card["model"] = label
    out["scaffold_card"] = card
    out["model"] = label
    return out


def _filter_metrics(rep: dict[str, Any], keep: set[str]) -> dict[str, Any]:
    if not keep:
        return rep
    out = dict(rep)
    out["gates"] = [g for g in (rep.get("gates") or []) if g.get("metric_id") in keep]
    out["bootstraps"] = [
        b for b in (rep.get("bootstraps") or []) if b.get("metric_id") in keep
    ]
    return out


def _metric_ids(rep: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for b in rep.get("bootstraps") or []:
        if b.get("metric_id"):
            ids.add(str(b["metric_id"]))
    for g in rep.get("gates") or []:
        mid = g.get("metric_id") or g.get("dimension")
        if mid:
            ids.add(str(mid))
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reports-dir", type=Path, default=Path("reports"))
    ap.add_argument("--level", type=float, default=0.5)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--models", default=None, help="Comma models (default: work/*)")
    ap.add_argument(
        "--include-incomplete-packs",
        action="store_true",
        help="Include packs without full k checkpoints",
    )
    args = ap.parse_args(argv)

    reports_dir = args.reports_dir.resolve()
    tag = f"bloat{int(round(args.level * 100))}"
    bloat_root = reports_dir / "bloat" / tag
    work_root = bloat_root / "work"
    if not work_root.is_dir():
        print(f"No bloat work dir at {work_root}", file=sys.stderr)
        return 1

    if args.models:
        models = [m.strip() for m in args.models.split(",") if m.strip()]
    else:
        models = sorted(
            p.name
            for p in work_root.iterdir()
            if p.is_dir() and not p.name.startswith(".")
        )

    all_packs = list_packs()
    bloat_reports: list[dict[str, Any]] = []
    pack_union: set[str] = set()

    for model in models:
        work = work_root / model.replace("/", "_")
        if not work.is_dir():
            print(f"  missing work dir {work}", file=sys.stderr)
            continue
        if args.include_incomplete_packs:
            packs = list(all_packs)
        else:
            packs = packs_complete_for_model(work, all_packs, args.k)
        pack_union.update(packs)
        rep = assemble_bloat_report(
            model=model, work=work, packs=packs, k=args.k, level=args.level
        )
        if not rep:
            print(f"  {model}: no scores assembled", file=sys.stderr)
            continue
        out_json = bloat_root / f"{model}.json"
        out_md = bloat_root / f"{model}.md"
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(json.dumps(rep, indent=2), encoding="utf-8")
        # Minimal MD so Reports UI has something
        try:
            from dsm_ae.models import DiagnosisReport

            out_md.write_text(
                render_markdown(DiagnosisReport.model_validate(rep)),
                encoding="utf-8",
            )
        except Exception:
            out_md.write_text(
                f"# {model} bloat{int(round(args.level*100))}\n\n"
                f"Packs: {', '.join(packs)}\n",
                encoding="utf-8",
            )
        rep["_source_path"] = str(out_json)
        bloat_reports.append(rep)
        print(
            f"  {model}: packs={len(packs)} gates={len(rep.get('gates') or [])} → {out_json}"
        )

    if not bloat_reports:
        print("No bloat reports to compare", file=sys.stderr)
        return 1

    bloat_metrics: set[str] = set()
    for rep in bloat_reports:
        bloat_metrics |= _metric_ids(rep)

    baseline_paths = discover_jsons([reports_dir])
    baseline_by_model: dict[str, list[dict[str, Any]]] = {}
    for p in baseline_paths:
        rep = load_report(p)
        if not rep:
            continue
        mid = model_id(rep)
        if mid in models:
            baseline_by_model.setdefault(mid, []).append(rep)

    labeled: list[dict[str, Any]] = []
    pct = int(round(args.level * 100))
    for model in models:
        for rep in baseline_by_model.get(model) or []:
            labeled.append(
                _relabel(_filter_metrics(rep, bloat_metrics), f"{model} · baseline")
            )
        if model not in baseline_by_model:
            print(f"  {model}: no baseline reports found", file=sys.stderr)

        bloat_rep = next(
            (r for r in bloat_reports if model_id(r) == model),
            None,
        )
        if bloat_rep is None:
            for r in bloat_reports:
                src = r.get("_source_path") or ""
                if model in Path(src).name:
                    bloat_rep = r
                    break
        if bloat_rep is not None:
            labeled.append(
                _relabel(
                    _filter_metrics(bloat_rep, bloat_metrics),
                    f"{model} · bloat{pct}%",
                )
            )

    if not labeled:
        print("Nothing to merge", file=sys.stderr)
        return 1

    by_model = merge_reports(labeled)
    ordered: dict[str, dict[str, Any]] = {}
    for model in models:
        for suffix in (f"{model} · baseline", f"{model} · bloat{pct}%"):
            if suffix in by_model:
                ordered[suffix] = by_model[suffix]
    for mid, acc in by_model.items():
        if mid not in ordered:
            ordered[mid] = acc

    title = (
        f"Context Bloat — baseline vs {pct}% "
        f"(complete packs only: {len(pack_union)})"
    )
    html_doc = build_html(ordered, title=title)
    out_html = bloat_root / "comparison.html"
    out_html.write_text(html_doc, encoding="utf-8")
    print(
        f"Wrote {out_html} ({len(ordered)} columns, {len(bloat_metrics)} metrics, "
        f"{len(pack_union)} packs)"
    )
    print(f"  columns: {', '.join(ordered.keys())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
