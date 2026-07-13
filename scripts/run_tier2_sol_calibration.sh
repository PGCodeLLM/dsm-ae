#!/usr/bin/env bash
# gpt-5.6-sol calibration: tier1 slop + erosion tier2 (+ optional tier3).
# Does NOT touch serve-queue. Safe to run while other jobs are live.
#
# Usage:
#   bash scripts/run_tier2_sol_calibration.sh
#   MODEL=gpt-5.6-sol K=2 J=2 bash scripts/run_tier2_sol_calibration.sh
#   DRY_RUN=1 bash scripts/run_tier2_sol_calibration.sh   # mock only
#   INCLUDE_TIER3=1 bash scripts/run_tier2_sol_calibration.sh
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="${MODEL:-gpt-5.6-sol}"
YAML="${YAML:-models.yaml}"
K="${K:-2}"
J="${J:-2}"
DRY_RUN="${DRY_RUN:-0}"
INCLUDE_TIER3="${INCLUDE_TIER3:-0}"

PACKS="slop_indicator,erosion_tier2"
if [[ "$INCLUDE_TIER3" == "1" ]]; then
  PACKS="${PACKS},erosion_tier3"
fi

OUT_DIR="reports/tier2"
WORK_ROOT="reports/work/tier2_sol"
LOG_DIR="logs/tier2"
mkdir -p "$OUT_DIR" "$WORK_ROOT" "$LOG_DIR"

safe_model="${MODEL//\//_}"
out_md="$OUT_DIR/${safe_model}-tier2-cal.md"
out_json="$OUT_DIR/${safe_model}-tier2-cal.json"
work="$WORK_ROOT/cal"
logf="$LOG_DIR/${safe_model}-cal.log"

echo "TIER2_SOL_CAL_START model=$MODEL packs=$PACKS k=$K j=$J dry_run=$DRY_RUN at=$(date -Is)" \
  | tee "$LOG_DIR/cal.log"

if [[ "$DRY_RUN" == "1" ]]; then
  echo "DRY_RUN: mock/well_attuned + mock/sloppy scoring smoke (no network)" | tee -a "$LOG_DIR/cal.log"
  python3 - <<'PY' | tee -a "$LOG_DIR/cal.log"
from dsm_ae.diagnose import diagnose
from dsm_ae.packs.registry import list_packs

assert "erosion_tier2" in list_packs()
assert "slop_indicator" in list_packs()
for persona in ("well_attuned", "sloppy"):
    r = diagnose(
        model=f"mock/{persona}",
        packs=["slop_indicator", "erosion_tier2", "erosion_tier3"],
        k=1,
        keep_traces=False,
        concurrency=1,
    )
    mids = {g.metric_id for g in r.gates}
    assert "erosion_indicator.tier1" in mids
    assert "erosion_indicator" in mids
    assert "erosion_indicator.tier2" in mids
    assert "erosion_indicator.tier3" in mids
    smoke_notes = [n for n in r.notes if "SMOKE/FLOOR" in n]
    assert smoke_notes, "expected smoke note in diagnosis notes"
    print(f"mock/{persona}: gates={len(r.gates)} findings_present={sum(1 for f in r.findings if f.present)}")
    for g in r.gates:
        if "erosion" in g.metric_id or "verbosity" in g.metric_id or "quality" in g.metric_id:
            print(f"  {g.metric_id}: status={g.status.value} pr={g.pass_rate:.2f} mean={g.mean:.3f}")
print("DRY_RUN_OK")
PY
  echo "TIER2_SOL_CAL_DRY_DONE $(date -Is)" | tee -a "$LOG_DIR/cal.log"
  exit 0
fi

if [[ ! -f "$YAML" ]]; then
  echo "ERROR: models yaml not found: $YAML" | tee -a "$LOG_DIR/cal.log"
  exit 1
fi

args=(
  dsm-ae diagnose
  -m "$MODEL"
  --models-yaml "$YAML"
  -p "$PACKS"
  --k "$K"
  -j "$J"
  --work-dir "$work"
  -o "$out_md"
  --json "$out_json"
)

echo "CMD: ${args[*]}" | tee -a "$LOG_DIR/cal.log"
set +e
"${args[@]}" >"$logf" 2>&1
ec=$?
set -e
echo "TIER2_SOL_CAL_EXIT=$ec at=$(date -Is)" | tee -a "$LOG_DIR/cal.log"
if [[ $ec -ne 0 ]]; then
  echo "FAILED — tail of $logf:" | tee -a "$LOG_DIR/cal.log"
  tail -50 "$logf" | tee -a "$LOG_DIR/cal.log"
  exit $ec
fi

python3 - << PY
import json
from pathlib import Path
p = Path("$out_json")
d = json.loads(p.read_text())
print(f"OK -> {p}")
print(f"  packs={d.get('packs')} k={d.get('k_trials')}")
for g in d.get("gates") or []:
    mid = g.get("metric_id")
    if mid and ("erosion" in mid or "verbosity" in mid or "quality" in mid or "god_" in mid or "extract" in mid):
        print(f"  {mid}: {g.get('status')} pr={g.get('pass_rate')} mean={g.get('mean')}")
notes = d.get("notes") or []
print("  smoke_notes:", [n for n in notes if "SMOKE" in n][:1])
PY

echo "TIER2_SOL_CAL_DONE $(date -Is)" | tee -a "$LOG_DIR/cal.log"
echo "Artifacts: $out_json $out_md work=$work log=$logf"
