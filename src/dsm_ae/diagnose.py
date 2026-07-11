"""Orchestrate packs × k bootstrap trials → report.

Concurrency:
  - Default concurrency=1 → fully sequential (stable).
  - concurrency=N → ThreadPoolExecutor runs up to N (pack, trial) jobs at once.
  - Optional rpm rate-limits *LLM-facing* job starts (not a pre-opened connection pool).
  - There is no long-lived connection pool per model; each job shares a ModelClient
    with a lock around complete() when concurrency > 1.
"""

from __future__ import annotations

import tempfile
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.criteria import evaluate_findings
from dsm_ae.litellm_client import ModelClient, make_client, resolve_from_models_yaml
from dsm_ae.metrics.bootstrap import bootstrap_metric, build_gate_matrix
from dsm_ae.models import DiagnosisReport, MetricResult, ScaffoldCard, TrialTrace
from dsm_ae.packs.registry import get_pack, list_packs
from dsm_ae.pool import RateLimiter, map_pool
from dsm_ae.report import render_markdown


class LockedClient(ModelClient):
    """Thread-safe wrapper around a ModelClient (serialize complete calls)."""

    def __init__(self, inner: ModelClient):
        self._inner = inner
        self._lock = threading.Lock()

    def complete(self, messages, tools=None, temperature=0.0, max_tokens=2048):
        with self._lock:
            return self._inner.complete(
                messages, tools=tools, temperature=temperature, max_tokens=max_tokens
            )

    def set_trial(self, i: int) -> None:
        if hasattr(self._inner, "set_trial"):
            with self._lock:
                self._inner.set_trial(i)  # type: ignore[attr-defined]


def _infer_rpm(
    models_yaml: Path | str | None, model: str, rpm: float | None
) -> float | None:
    if rpm is not None:
        return rpm
    if not models_yaml:
        return None
    try:
        entry = resolve_from_models_yaml(models_yaml, model)
        params = entry.get("litellm_params") or {}
        v = params.get("rpm")
        return float(v) if v is not None else None
    except Exception:
        return None


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
    models_yaml: Path | str | None = None,
    api_base: str | None = None,
    api_key: str | None = None,
    max_turns: int = 10,
    concurrency: int = 1,
    rpm: float | None = None,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
    client_extra: dict[str, Any] | None = None,
) -> DiagnosisReport:
    packs = packs or list_packs()
    inferred_rpm = _infer_rpm(models_yaml, model, rpm)
    card = ScaffoldCard(
        model=model,
        scaffold=scaffold,
        permission_mode=permission_mode,
        k_trials=k,
        max_turns=max_turns,
        extra={
            "models_yaml": str(models_yaml) if models_yaml else None,
            "api_base": api_base,
            "concurrency": concurrency,
            "rpm": inferred_rpm,
        },
    )
    raw_client: ModelClient = make_client(
        model,
        mock_persona=mock_persona,
        models_yaml=models_yaml,
        api_base=api_base,
        api_key=api_key,
        extra=client_extra,
    )
    client: ModelClient = (
        LockedClient(raw_client) if concurrency and concurrency > 1 else raw_client
    )
    adapter = RawToolLoopAdapter(client, card)

    root = Path(work_dir) if work_dir else Path(tempfile.mkdtemp(prefix="dsm_ae_"))
    root.mkdir(parents=True, exist_ok=True)

    notes: list[str] = [
        f"Work dir: {root}",
        f"Packs: {packs}",
        "Indicator protocols only (not full SlopCodeBench/OverEager-Bench).",
        f"Disorder if pass_rate < {threshold_pass} OR std > {threshold_std}.",
        f"Concurrency={concurrency} (N workers for pack×trial jobs; default 1=sequential).",
        f"RPM limit={inferred_rpm if inferred_rpm else 'none'} (job-start spacing, not connection pool).",
    ]

    jobs: list[tuple[str, int]] = [
        (pack_id, trial_i) for pack_id in packs for trial_i in range(k)
    ]
    total = len(jobs)
    done_lock = threading.Lock()
    done_count = 0

    def _emit(payload: dict[str, Any]) -> None:
        if on_progress is None:
            return
        try:
            on_progress(payload)
        except Exception:
            pass

    _emit(
        {
            "phase": "starting",
            "status": "running",
            "done": 0,
            "total": total,
            "message": f"Starting {total} pack×trial jobs",
            "packs": list(packs),
            "k": k,
        }
    )

    limiter = RateLimiter(inferred_rpm)

    def _run_job(job: tuple[str, int]) -> list[tuple[str, TrialTrace, list[MetricResult]]]:
        nonlocal done_count
        pack_id, trial_i = job
        pack = get_pack(pack_id)
        # set_trial for mock personas
        if hasattr(client, "set_trial"):
            client.set_trial(trial_i)  # type: ignore[attr-defined]
        elif hasattr(raw_client, "set_trial"):
            raw_client.set_trial(trial_i)  # type: ignore[attr-defined]
        traces = pack.run_trial(adapter, root / pack_id, trial_i)
        out: list[tuple[str, TrialTrace, list[MetricResult]]] = []
        for tr in traces:
            out.append((pack_id, tr, pack.score(tr)))
        with done_lock:
            done_count += 1
            cur = done_count
        _emit(
            {
                "phase": "running",
                "status": "running",
                "done": cur,
                "total": total,
                "current_pack": pack_id,
                "current_trial": trial_i,
                "message": f"{pack_id} trial {trial_i + 1}/{k} complete ({cur}/{total})",
            }
        )
        return out

    # Rate limit is applied at job start when concurrency>1 via map_pool
    nested = map_pool(
        jobs,
        _run_job,
        concurrency=concurrency,
        rate_limiter=limiter if concurrency > 1 else None,
    )

    all_traces: list[TrialTrace] = []
    bucket: dict[str, list[MetricResult]] = {}
    for batch in nested:
        for _pack_id, tr, scores in batch:
            all_traces.append(tr)
            for m in scores:
                bucket.setdefault(m.metric_id, []).append(m)

    _emit(
        {
            "phase": "scoring",
            "status": "running",
            "done": total,
            "total": total,
            "message": "Scoring metrics and findings",
        }
    )

    bootstraps = [
        bootstrap_metric(
            mid,
            mid,
            results,
            threshold_pass=threshold_pass,
            threshold_std=threshold_std,
        )
        for mid, results in bucket.items()
    ]
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
    _emit(
        {
            "phase": "done",
            "status": "succeeded",
            "done": total,
            "total": total,
            "message": "Diagnosis complete",
            "findings_present": sum(1 for f in findings if f.present),
        }
    )
    return report


def diagnose_to_markdown(**kwargs: Any) -> tuple[DiagnosisReport, str]:
    report = diagnose(**kwargs)
    return report, render_markdown(report)
