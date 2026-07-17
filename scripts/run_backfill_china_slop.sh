#!/usr/bin/env bash
# Backfill slop_indicator (.tier1 dual-emit) for china-host models.
# Wait until run_repro_china_resume is not running.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
LOG=logs/backfill_china_slop.log
mkdir -p logs reports/backfill work/backfill

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

wait_resume_idle() {
  while pgrep -f 'run_repro_china_resume.py' >/dev/null 2>&1; do
    log "waiting for run_repro_china_resume to finish..."
    sleep 60
  done
  # also wait until no china diagnose still running
  while pgrep -f 'dsm-ae diagnose -m (glm|deepseek|qwen)' >/dev/null 2>&1; do
    log "waiting for residual china diagnose to finish..."
    sleep 30
  done
}

run_one() {
  local model="$1"
  local packs="$2"
  local safe
  safe=$(echo "$model" | tr './' '_')
  log "START $model packs=$packs"
  dsm-ae diagnose -m "$model" --models-yaml models.yaml \
    -p "$packs" --k 10 -j 1 --rpm 4 \
    --work-dir "work/backfill/${safe}" \
    --out "reports/backfill/${safe}.md" \
    --json "reports/backfill/${safe}.json" \
    >>"$LOG" 2>&1
  local rc=$?
  log "DONE $model rc=$rc"
  return $rc
}

wait_resume_idle
log "china host free — starting slop_indicator (+injection if needed) backfill"

# All china models need slop_indicator for .tier1 dual-emit
for M in glm-5.1 glm-5.2 deepseek-v4-pro qwen3.6-plus qwen3.7-max qwen3.5-397b-a17b; do
  run_one "$M" slop_indicator || true
done

# critical_preserved.tier1 if still missing after china resume injection_mini
# Re-run injection_mini for models that still lack it (cheap check via python)
python3 - <<'PY' > /tmp/need_injection.txt
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("jth", "scripts/json_to_html_report.py")
jth = importlib.util.module_from_spec(spec); spec.loader.exec_module(jth)
paths = jth.discover_jsons([Path('reports')])
reports = [r for p in paths if (r := jth.load_report(p))]
by_model = jth.merge_reports(reports)
for m in ["glm-5.1","glm-5.2","deepseek-v4-pro","qwen3.6-plus","qwen3.7-max","qwen3.5-397b-a17b"]:
    if m not in by_model: 
        print(m); continue
    if "critical_preserved.tier1" not in by_model[m]["gates"]:
        print(m)
PY

while read -r M; do
  [ -z "$M" ] && continue
  run_one "$M" injection_mini || true
done < /tmp/need_injection.txt

log "CHINA BACKFILL COMPLETE"
