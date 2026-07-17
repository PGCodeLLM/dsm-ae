#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
LOG=logs/backfill_proxy.log
mkdir -p logs reports/backfill work/backfill

log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

run_one() {
  local model="$1"
  local packs="$2"
  local rpm="${3:-6}"
  local safe
  safe=$(echo "$model" | tr './' '_')
  log "START $model packs=$packs"
  dsm-ae diagnose -m "$model" --models-yaml models.yaml \
    -p "$packs" --k 10 -j 2 --rpm "$rpm" \
    --work-dir "work/backfill/${safe}" \
    --out "reports/backfill/${safe}.md" \
    --json "reports/backfill/${safe}.json" \
    >>"$LOG" 2>&1
  local rc=$?
  log "DONE $model rc=$rc"
  return $rc
}

# Complete first: cheap single-pack models
run_one gpt-5.6-luna slop_indicator 6 || true
run_one gpt-5.6-terra slop_indicator 6 || true

# Multi-pack gaps (tier1 dual-emit + critical_preserved.tier1 + tool_integrity_tier2)
PACKS_FULL="slop_indicator,injection_mini,tool_integrity_tier2"
run_one gpt-5.4-mini "$PACKS_FULL" 6 || true
run_one claude-sonnet-5 "$PACKS_FULL" 6 || true
run_one claude-opus-4-8 "$PACKS_FULL" 6 || true
run_one claude-fable-5 "$PACKS_FULL" 6 || true

log "ALL PROXY BACKFILL COMPLETE"
