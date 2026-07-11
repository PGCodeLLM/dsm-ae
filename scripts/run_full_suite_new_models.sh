#!/usr/bin/env bash
# Full-suite for gpt-5.6-{terra,sol,luna}; retry grok missing packs.
set -uo pipefail
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
export PYTHONUNBUFFERED=1
LOG=logs/full_suite_new_models.log
mkdir -p logs reports/full-suite work

# all registered packs
PACKS=$(PYTHONPATH=src python3 -c "from dsm_ae.packs.registry import list_packs; print(','.join(list_packs()))")
MODELS=(gpt-5.6-terra gpt-5.6-sol gpt-5.6-luna)
# packs grok still missing from JSON union
GROK_MISSING="memory_context,handoff_mini,eval_gaming_mini,sandbag_mini,clarify_verify,pii_safety,nfr_omit"

echo "===== START $(date -Is) =====" | tee -a "$LOG"
echo "PACKS=$PACKS" | tee -a "$LOG"

run_proxy() {
  local model="$1"
  local packs="$2"
  local tag="$3"
  local safe
  safe=$(echo "$model" | tr './' '_')
  echo "===== $model tag=$tag $(date -Is) =====" | tee -a "$LOG"
  dsm-ae diagnose -m "$model" --models-yaml models.yaml \
    -p "$packs" --k 3 -j 2 --rpm 6 \
    --work-dir "work/fs_${safe}_${tag}" \
    --out "reports/full-suite/${safe}-${tag}.md" \
    --json "reports/full-suite/${safe}-${tag}.json" \
    >>"$LOG" 2>&1
  local rc=$?
  echo "===== DONE $model tag=$tag rc=$rc $(date -Is) =====" | tee -a "$LOG"
  return $rc
}

run_grok() {
  local packs="$1"
  local tag="$2"
  echo "===== grok-build tag=$tag $(date -Is) =====" | tee -a "$LOG"
  PACKS_CSV="$packs" OUT_TAG="$tag" PYTHONPATH=src python3 - <<'PY' >>"$LOG" 2>&1
import json, os, sys, traceback
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
        "timeout": 180,
        "num_retries": 3,
        "extra_headers": {
            "User-Agent": "grok/0.2.95",
            "x-grok-client-version": "0.2.95",
            "x-grok-client-surface": "cli",
        },
    },
)
lc.make_client = dm.make_client = lambda *a, **k: client
try:
    report = diagnose(
        model="grok-build",
        packs=packs,
        k=3,
        concurrency=2,
        work_dir=Path(f"work/fs_grok_{tag}"),
    )
    out = Path("reports/full-suite")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"grok-build-{tag}.md").write_text(render_markdown(report), encoding="utf-8")
    (out / f"grok-build-{tag}.json").write_text(
        report.model_dump_json(indent=2), encoding="utf-8"
    )
    print(f"grok-build {tag} done: gates={len(report.gates)} findings={len(report.findings)}")
except Exception:
    traceback.print_exc()
    sys.exit(1)
PY
  local rc=$?
  echo "===== DONE grok-build tag=$tag rc=$rc $(date -Is) =====" | tee -a "$LOG"
  return $rc
}

for M in "${MODELS[@]}"; do
  run_proxy "$M" "$PACKS" full || echo "FAIL $M" | tee -a "$LOG"
done

# Retry grok missing packs (up to 2 attempts)
for attempt in 1 2; do
  echo "===== grok retry attempt $attempt =====" | tee -a "$LOG"
  if run_grok "$GROK_MISSING" "wave2-retry${attempt}"; then
    break
  fi
  sleep 30
done

echo "===== ALL COMPLETE $(date -Is) =====" | tee -a "$LOG"

# regenerate HTML matrix from all reports
PYTHONPATH=src python3 scripts/json_to_html_report.py reports -o reports/dsm-ae-matrix.html >>"$LOG" 2>&1 || true
echo "===== HTML regenerated $(date -Is) =====" | tee -a "$LOG"
