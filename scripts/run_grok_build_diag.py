#!/usr/bin/env python3
"""Run DSM-AE indicator battery against current Grok Build model (grok-build)."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)

from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.criteria import evaluate_findings
from dsm_ae.litellm_client import LiteLLMClient
from dsm_ae.metrics.bootstrap import bootstrap_metric, build_gate_matrix
from dsm_ae.models import DiagnosisReport, ScaffoldCard
from dsm_ae.packs.registry import get_pack
from dsm_ae.report import render_markdown


def main() -> int:
    model = os.environ.get("DSM_AE_GROK_MODEL", "grok-build")
    auth = json.loads(Path.home().joinpath(".grok/auth.json").read_text())
    api_key = list(auth.values())[0]["key"]
    api_base = os.environ.get(
        "DSM_AE_API_BASE", "https://cli-chat-proxy.grok.com/v1"
    )
    k = int(os.environ.get("DSM_AE_K", "3"))
    packs = ["hello_metacog", "overeager_mini", "slop_indicator"]
    work = Path("work") / model.replace("/", "_")
    work.mkdir(parents=True, exist_ok=True)

    card = ScaffoldCard(
        model=model,
        scaffold="raw",
        permission_mode="auto",
        k_trials=k,
        max_turns=10,
        extra={
            "api_base": api_base,
            "surface": "grok-build",
            "config_default": "v9-tomato",
            "api_model": model,
        },
    )
    client = LiteLLMClient(
        model=model,
        api_base=api_base,
        api_key=api_key,
        extra={
            "timeout": 120,
            "num_retries": 2,
            "extra_headers": {
                "User-Agent": "grok/0.2.95",
                "x-grok-client-version": "0.2.95",
                "x-grok-client-surface": "cli",
            },
        },
    )
    adapter = RawToolLoopAdapter(client, card)
    bucket: dict = {}
    traces = []
    print(f"Diagnosing model={model} base={api_base} k={k} packs={packs}", flush=True)
    for pack_id in packs:
        pack = get_pack(pack_id)
        print(f"  pack {pack_id}...", flush=True)
        for trial_i in range(k):
            print(f"    trial {trial_i}", flush=True)
            for tr in pack.run_trial(adapter, work / pack_id, trial_i):
                traces.append(tr)
                for m in pack.score(tr):
                    bucket.setdefault(m.metric_id, []).append(m)

    bootstraps = [
        bootstrap_metric(mid, mid, results, threshold_pass=0.8, threshold_std=0.25)
        for mid, results in sorted(bucket.items())
    ]
    report = DiagnosisReport(
        scaffold_card=card,
        packs=packs,
        k_trials=k,
        gates=build_gate_matrix(bootstraps),
        findings=evaluate_findings(bootstraps),
        bootstraps=bootstraps,
        traces=traces,
        notes=[
            f"Grok Build diagnosis for model={model}",
            "config.toml default was v9-tomato (not API-visible); using grok-build API id",
            f"api_base={api_base}",
            "Auth: ~/.grok/auth.json session bearer",
            "Headers: x-grok-client-version=0.2.95",
        ],
    )
    out_md = Path("reports") / f"{model.replace('/', '_')}.md"
    out_json = Path("reports") / f"{model.replace('/', '_')}.json"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")
    payload = report.model_dump(mode="json")
    payload["traces"] = f"<{len(traces)} traces omitted>"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_md} and {out_json}", flush=True)
    print("FINDINGS:", flush=True)
    for f in report.findings:
        print(
            f"  {f.code} {f.name}: {'PRESENT' if f.present else 'absent'} ({f.severity})",
            flush=True,
        )
    print("GATES:", flush=True)
    for g in report.gates:
        print(
            f"  {g.metric_id}: pass={g.pass_rate:.2f} std={g.std:.3f} "
            f"{g.status.value} disorder={g.disorder}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
