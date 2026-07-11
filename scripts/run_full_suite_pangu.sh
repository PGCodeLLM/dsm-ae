#!/usr/bin/env bash
# Full suite for Beta_pangu_92b and Beta_pangu_505b
set -uo pipefail
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
export PYTHONUNBUFFERED=1
LOG=logs/full_suite_pangu.log
mkdir -p logs reports/full-suite work

PACKS=$(PYTHONPATH=src python3 -c "from dsm_ae.packs.registry import list_packs; print(','.join(list_packs()))")
MODELS=(Beta_pangu_92b Beta_pangu_505b)

echo "===== START $(date -Is) =====" | tee -a "$LOG"
echo "PACKS=$PACKS" | tee -a "$LOG"
echo "MODELS=${MODELS[*]}" | tee -a "$LOG"

run_proxy() {
  local model="$1"
  local safe
  safe=$(echo "$model" | tr './' '_')
  echo "===== $model full $(date -Is) =====" | tee -a "$LOG"
  # rpm from models.yaml (10); concurrency 2
  dsm-ae diagnose -m "$model" --models-yaml models.yaml \
    -p "$PACKS" --k 3 -j 2 --rpm 10 \
    --work-dir "work/fs_${safe}_full" \
    --out "reports/full-suite/${safe}-full.md" \
    --json "reports/full-suite/${safe}-full.json" \
    >>"$LOG" 2>&1
  local rc=$?
  echo "===== DONE $model rc=$rc $(date -Is) =====" | tee -a "$LOG"
  return $rc
}

for M in "${MODELS[@]}"; do
  run_proxy "$M" || echo "FAIL $M" | tee -a "$LOG"
done

echo "===== ALL COMPLETE $(date -Is) =====" | tee -a "$LOG"
PYTHONPATH=src python3 scripts/json_to_html_report.py reports -o reports/dsm-ae-matrix.html >>"$LOG" 2>&1 || true
echo "===== HTML regenerated $(date -Is) =====" | tee -a "$LOG"
