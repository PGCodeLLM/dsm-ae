#!/bin/bash
# Run remaining multi-agent packs (+ missing wave2) for all models.
set -uo pipefail
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
export PYTHONUNBUFFERED=1
mkdir -p logs reports/ma-packs work

MA_PACKS="role_confusion_mini,mas_verify_mini,session_overwrite_mini,coord_tax_mini"
WAVE2="memory_context,handoff_mini,eval_gaming_mini,sandbag_mini,clarify_verify,pii_safety,nfr_omit"
LOG=logs/ma_remaining.log
echo "===== START $(date -Is) =====" | tee -a "$LOG"

run_proxy() {
  local model="$1"
  local packs="$2"
  local out_tag="$3"
  local safe
  safe=$(echo "$model" | tr './' '_')
  echo "===== $model packs=$packs $(date -Is) =====" | tee -a "$LOG"
  dsm-ae diagnose -m "$model" --models-yaml models.yaml \
    -p "$packs" --k 3 -j 2 --rpm 6 \
    --work-dir "work/ma_${safe}_${out_tag}" \
    --out "reports/ma-packs/${safe}-${out_tag}.md" \
    --json "reports/ma-packs/${safe}-${out_tag}.json" \
    >>"$LOG" 2>&1
  local rc=$?
  echo "===== DONE $model tag=$out_tag rc=$rc $(date -Is) =====" | tee -a "$LOG"
  return $rc
}

run_grok() {
  local packs="$1"
  local out_tag="$2"
  echo "===== grok-build packs=$packs $(date -Is) =====" | tee -a "$LOG"
  PACKS_CSV="$packs" OUT_TAG="$out_tag" PYTHONPATH=src python3 - <<'PY' >>"$LOG" 2>&1
import json, os, sys
from pathlib import Path
os.chdir("/home/arcyleung/Projects/grok_trace_analysis/dsm-ae")
sys.path.insert(0, "src")
from dsm_ae.diagnose import diagnose
from dsm_ae.report import render_markdown
from dsm_ae.litellm_client import LiteLLMClient
from dsm_ae import litellm_client as lc, diagnose as dm

packs = [p.strip() for p in os.environ["PACKS_CSV"].split(",") if p.strip()]
tag = os.environ["OUT_TAG"]
auth = json.loads(Path.home().joinpath(".grok/auth.json").read_text())
key = list(auth.values())[0]["key"]
client = LiteLLMClient(
    model="grok-build",
    api_base="https://cli-chat-proxy.grok.com/v1",
    api_key=key,
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
lc.make_client = dm.make_client = lambda *a, **k: client
report = diagnose(
    model="grok-build",
    packs=packs,
    k=3,
    concurrency=2,
    work_dir=Path(f"work/ma_grok_{tag}"),
)
out = Path("reports/ma-packs")
out.mkdir(parents=True, exist_ok=True)
(out / f"grok-build-{tag}.md").write_text(render_markdown(report), encoding="utf-8")
(out / f"grok-build-{tag}.json").write_text(
    report.model_dump_json(indent=2), encoding="utf-8"
)
print(f"grok-build {tag} done: gates={len(report.gates)} findings={len(report.findings)}")
PY
  echo "===== DONE grok-build tag=$out_tag rc=$? $(date -Is) =====" | tee -a "$LOG"
}

# 1) Multi-agent remaining packs for all models
run_proxy gpt-5.5 "$MA_PACKS" ma || true
run_proxy gpt-5.4-mini "$MA_PACKS" ma || true
run_grok "$MA_PACKS" ma || true

# 2) Wave2 gaps (not yet on mini/grok)
if [[ ! -f reports/new-packs/gpt-5.4-mini-wave2.json ]]; then
  run_proxy gpt-5.4-mini "$WAVE2" wave2 || true
fi
if [[ ! -f reports/new-packs/grok-build-wave2.json && ! -f reports/ma-packs/grok-build-wave2.json ]]; then
  run_grok "$WAVE2" wave2 || true
fi

echo "===== ALL COMPLETE $(date -Is) =====" | tee -a "$LOG"
