"""Orchestrate packs × k bootstrap trials → report."""

from __future__ import annotations

import tempfile
from pathlib import Path

from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.criteria import evaluate_findings
from dsm_ae.litellm_client import ModelClient, make_client
from dsm_ae.metrics.bootstrap import bootstrap_metric, build_gate_matrix
from dsm_ae.models import (
    DiagnosisReport,
    MetricResult,
    ScaffoldCard,
    TrialTrace,
)
from dsm_ae.packs.registry import get_pack, list_packs
from dsm_ae.report import render_markdown


def diagnose(
    *,
    model: str,
    packs: list[str] | None = None,
    k: int = 5,
    scaffold: str = "raw",
    permission_mode: str = "auto",
    work_dir: Path | None = None,
    mock_persona: str | None = None,
    threshold_pass: float = 0.8,
    threshold_std: float = 0.25,
    keep_traces: bool = True,
) -> DiagnosisReport:
    packs = packs or list_packs()
    card = ScaffoldCard(
        model=model,
        scaffold=scaffold,
        permission_mode=permission_mode,
        k_trials=k,
    )
    client: ModelClient = make_client(model, mock_persona=mock_persona)
    adapter = RawToolLoopAdapter(client, card)

    root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="dsm_ae_"))
    root.mkdir(parents=True, exist_ok=True)

    all_traces: list[TrialTrace] = []
    # metric_id -> list of MetricResult across trials (and variants)
    bucket: dict[str, list[MetricResult]] = {}
    dimension_for: dict[str, str] = {}

    notes: list[str] = [
        f"Work dir: {root}",
        f"Packs: {packs}",
        "Indicator protocols only (not full SlopCodeBench/OverEager-Bench).",
        f"Disorder if pass_rate < {threshold_pass} OR std > {threshold_std}.",
    ]

    for pack_id in packs:
        pack = get_pack(pack_id)
        for trial_i in range(k):
            traces = pack.run_trial(adapter, root / pack_id, trial_i)
            for tr in traces:
                all_traces.append(tr)
                for m in pack.score(tr):
                    bucket.setdefault(m.metric_id, []).append(m)
                    dimension_for.setdefault(m.metric_id, m.metric_id)

    bootstraps = []
    for mid, results in bucket.items():
        # dimension = pack dimension name if matches else metric id
        dim = mid
        bootstraps.append(
            bootstrap_metric(
                mid,
                dim,
                results,
                threshold_pass=threshold_pass,
                threshold_std=threshold_std,
            )
        )

    # stable order
    bootstraps.sort(key=lambda b: b.metric_id)
    gates = build_gate_matrix(bootstraps)
    findings = evaluate_findings(bootstraps)

    report = DiagnosisReport(
        scaffold_card=card,
        packs=packs,
        k_trials=k,
        gates=gates,
        findings=findings,
        bootstraps=bootstraps,
        traces=all_traces if keep_traces else [],
        notes=notes,
    )
    return report


def diagnose_to_markdown(**kwargs) -> tuple[DiagnosisReport, str]:
    report = diagnose(**kwargs)
    return report, render_markdown(report)
