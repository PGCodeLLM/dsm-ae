#!/usr/bin/env python3
from __future__ import annotations
import json, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
os.chdir(ROOT)
from dsm_ae.diagnose import diagnose
from dsm_ae.report import render_markdown
from dsm_ae.litellm_client import LiteLLMClient
from dsm_ae.adapters.raw_loop import RawToolLoopAdapter
from dsm_ae.models import ScaffoldCard
from dsm_ae.packs.registry import get_pack
from dsm_ae.metrics.bootstrap import bootstrap_metric, build_gate_matrix
from dsm_ae.criteria import evaluate_findings
from dsm_ae.models import DiagnosisReport
from dsm_ae.pool import RateLimiter, map_pool
import threading

def main():
    model = "grok-build"
    auth = json.loads(Path.home().joinpath(".grok/auth.json").read_text())
    api_key = list(auth.values())[0]["key"]
    api_base = "https://cli-chat-proxy.grok.com/v1"
    packs = ["loop_control","tool_integrity","sycophancy_mini","injection_mini","gate_discipline"]
    k = int(os.environ.get("DSM_AE_K", "3"))
    concurrency = int(os.environ.get("DSM_AE_CONCURRENCY", "2"))
    work = Path("work/np_grok"); work.mkdir(parents=True, exist_ok=True)
    card = ScaffoldCard(model=model, scaffold="raw", k_trials=k, max_turns=10,
                        extra={"api_base": api_base, "concurrency": concurrency})
    client = LiteLLMClient(model=model, api_base=api_base, api_key=api_key, extra={
        "timeout": 120, "num_retries": 2,
        "extra_headers": {"User-Agent":"grok/0.2.95","x-grok-client-version":"0.2.95","x-grok-client-surface":"cli"},
    })
    # use diagnose() path by temporarily monkeypatching make_client is hard;
    # call diagnose with api_base/key via env... diagnose uses make_client
    # Instead set os.environ and use a thin path: use diagnose with models_yaml None
    # but need grok headers - extend make_client or call diagnose after patching.
    from dsm_ae import diagnose as diagnose_mod
    from dsm_ae import litellm_client as lc
    orig = lc.make_client
    def make_client_grok(model, mock_persona=None, **kw):
        return client
    lc.make_client = make_client_grok
    diagnose_mod.make_client = make_client_grok
    try:
        report = diagnose(
            model=model, packs=packs, k=k, concurrency=concurrency,
            work_dir=work, max_turns=10, keep_traces=True,
        )
    finally:
        lc.make_client = orig
        diagnose_mod.make_client = orig
    out_md = Path("reports/new-packs/grok-build.md")
    out_json = Path("reports/new-packs/grok-build.json")
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(render_markdown(report), encoding="utf-8")
    payload = report.model_dump(mode="json")
    payload["traces"] = f"<{len(report.traces)} traces omitted>"
    out_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_md}")
    for f in report.findings:
        print(f"{f.code}: {'PRESENT' if f.present else 'absent'} ({f.severity})")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
