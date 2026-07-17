#!/usr/bin/env bash
# Reproducibility study: shared syndromes for gpt-5.5 + grok-build, k=10 each.
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1

MODELS=(gpt-5.5 grok-build)
# syndrome_code:pack
declare -a CELLS=(
  "CTX:coord_tax_mini"
  "MAH:handoff_mini"
  "MCD:hello_metacog"
  "PCD:loop_control"
  "TID:tool_integrity"
  "RSD:sycophancy_mini"
  "ISDS:slop_indicator"
)

K="${K:-10}"
J="${J:-2}"
YAML="${YAML:-models.yaml}"
OUT_ROOT="${OUT_ROOT:-reports/repro-shared}"
WORK_ROOT="${WORK_ROOT:-work/repro-shared}"
LOG="${LOG:-logs/repro_shared_symptoms.log}"
mkdir -p "$OUT_ROOT" "$WORK_ROOT" logs

echo "===== REPRO START $(date -Is) K=$K J=$J =====" | tee -a "$LOG"

rpm_for() {
  case "$1" in
    gpt-5.5) echo 6 ;;
    grok-build) echo 4 ;;
    *) echo 4 ;;
  esac
}

for model in "${MODELS[@]}"; do
  mkdir -p "$OUT_ROOT/$model" "$WORK_ROOT/$model"
  for cell in "${CELLS[@]}"; do
    code="${cell%%:*}"
    pack="${cell##*:}"
    safe_pack="${pack//\//_}"
    out_md="$OUT_ROOT/$model/${code}_${safe_pack}.md"
    out_json="$OUT_ROOT/$model/${code}_${safe_pack}.json"
    work="$WORK_ROOT/$model/${safe_pack}"
    rpm=$(rpm_for "$model")
    echo "===== $model $code pack=$pack k=$K $(date -Is) =====" | tee -a "$LOG"
    if dsm-ae diagnose \
        -m "$model" \
        --models-yaml "$YAML" \
        -p "$pack" \
        --k "$K" \
        -j "$J" \
        --rpm "$rpm" \
        --work-dir "$work" \
        --out "$out_md" \
        --json "$out_json" \
        >>"$LOG" 2>&1; then
      echo "OK $model $code" | tee -a "$LOG"
    else
      echo "FAIL $model $code rc=$?" | tee -a "$LOG"
    fi
  done
done

echo "===== SUMMARIZE $(date -Is) =====" | tee -a "$LOG"
PYTHONPATH=src python3 scripts/summarize_repro_shared.py \
  --root "$OUT_ROOT" --out "$OUT_ROOT/SUMMARY.md" 2>&1 | tee -a "$LOG"

echo "===== REPRO DONE $(date -Is) =====" | tee -a "$LOG"
