#!/usr/bin/env bash
set -euo pipefail
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
export PYTHONUNBUFFERED=1
LOG=reports/batch-extra-models.log
mkdir -p reports work

# Wait for in-flight gpt-5.4-mini if still running
while pgrep -f 'dsm-ae diagnose -m gpt-5.4-mini' >/dev/null 2>&1; do
  echo "$(date -Is) waiting for gpt-5.4-mini to finish..." | tee -a "$LOG"
  sleep 20
done

MODELS=(gpt-5.4 gpt-5.6-terra gpt-5.6-luna gpt-5.6-sol)
# If mini failed earlier, include it
if [[ ! -f reports/gpt-5.4-mini.md ]]; then
  MODELS=(gpt-5.4-mini "${MODELS[@]}")
fi

for M in "${MODELS[@]}"; do
  SAFE=$(echo "$M" | tr './' '__')
  echo "===== START $M $(date -Is) =====" | tee -a "$LOG"
  if dsm-ae diagnose \
      -m "$M" \
      --models-yaml models.yaml \
      --k 3 \
      -p hello_metacog,overeager_mini,slop_indicator \
      --work-dir "work/$SAFE" \
      --out "reports/${M}.md" \
      --json "reports/${M}.json" \
      >>"$LOG" 2>&1; then
    echo "===== END $M exit=0 $(date -Is) =====" | tee -a "$LOG"
    echo "SUCCESS $M" > "reports/${M}-STATUS.txt"
  else
    EC=$?
    echo "===== END $M exit=$EC $(date -Is) =====" | tee -a "$LOG"
    echo "FAIL $M exit=$EC" > "reports/${M}-STATUS.txt"
  fi
done

echo "===== BATCH COMPLETE $(date -Is) =====" | tee -a "$LOG"
# Write comparison table
python3 scripts/summarize_reports.py || true
