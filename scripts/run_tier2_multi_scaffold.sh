#!/usr/bin/env bash
# Multi-scaffold stability harness for erosion tier2 (and optional tier3).
# Same pack under baseline / prompt_reminder / skill_scaffold / expert_oversight.
# Pattern mirrors run_treatment_luna_trial.sh but targets sol + tier2 packs.
#
# Usage:
#   bash scripts/run_tier2_multi_scaffold.sh
#   MODEL=gpt-5.6-sol K=2 bash scripts/run_tier2_multi_scaffold.sh
#   DRY_RUN=1 bash scripts/run_tier2_multi_scaffold.sh
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="${MODEL:-gpt-5.6-sol}"
YAML="${YAML:-models.yaml}"
K="${K:-2}"
J="${J:-2}"
DRY_RUN="${DRY_RUN:-0}"
PACKS="${PACKS:-erosion_tier2,slop_indicator}"
OUT_DIR="reports/tier2/scaffold"
WORK_ROOT="reports/work/tier2_scaffold"
LOG_DIR="logs/tier2/scaffold"
mkdir -p "$OUT_DIR" "$WORK_ROOT" "$LOG_DIR"

ARMS=("" "prompt_reminder" "skill_scaffold" "expert_oversight")
NAMES=("baseline" "prompt_reminder" "skill_scaffold" "expert_oversight")
safe_model="${MODEL//\//_}"

echo "TIER2_SCAFFOLD_START model=$MODEL packs=$PACKS k=$K dry_run=$DRY_RUN at=$(date -Is)" \
  | tee "$LOG_DIR/run.log"

if [[ "$DRY_RUN" == "1" ]]; then
  python3 - <<'PY' | tee -a "$LOG_DIR/run.log"
from dsm_ae.diagnose import diagnose
from dsm_ae.treatment import list_treatments

print("treatments:", list_treatments() if hasattr(__import__("dsm_ae.treatment", fromlist=["list_treatments"]), "list_treatments") else "see get_treatment")
try:
    from dsm_ae.treatment import get_treatment
    for t in ("prompt_reminder", "skill_scaffold", "expert_oversight"):
        get_treatment(t)
        print(f"  treatment ok: {t}")
except Exception as e:
    print("treatment import note:", e)

r = diagnose(
    model="mock/well_attuned",
    packs=["erosion_tier2", "slop_indicator"],
    k=1,
    keep_traces=False,
    treatment=None,
)
assert any(g.metric_id == "erosion_indicator.tier2" for g in r.gates)
print("DRY_RUN_OK baseline mock gates", len(r.gates))
PY
  echo "TIER2_SCAFFOLD_DRY_DONE $(date -Is)" | tee -a "$LOG_DIR/run.log"
  exit 0
fi

for i in "${!ARMS[@]}"; do
  arm="${ARMS[$i]}"
  name="${NAMES[$i]}"
  out_md="$OUT_DIR/${safe_model}-${name}.md"
  out_json="$OUT_DIR/${safe_model}-${name}.json"
  work="$WORK_ROOT/${name}"
  logf="$LOG_DIR/${name}.log"
  echo "=== ARM $name start $(date -Is) ===" | tee -a "$LOG_DIR/run.log"
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
  if [[ -n "$arm" ]]; then
    args+=(--treatment "$arm")
  fi
  set +e
  "${args[@]}" >"$logf" 2>&1
  ec=$?
  set -e
  echo "=== ARM $name exit=$ec $(date -Is) ===" | tee -a "$LOG_DIR/run.log"
  if [[ $ec -ne 0 ]]; then
    tail -40 "$logf" | tee -a "$LOG_DIR/run.log"
  else
    python3 - << PY
import json
from pathlib import Path
p=Path("$out_json")
d=json.loads(p.read_text())
for g in d.get("gates") or []:
    mid=g.get("metric_id") or ""
    if "erosion" in mid or mid in ("extract_discipline","god_function_mass"):
        print(f"  {mid}: {g.get('status')} pr={g.get('pass_rate')} mean={g.get('mean')}")
PY
  fi
done

python3 - << PY
import json
from pathlib import Path
out = Path("$OUT_DIR")
model = "$safe_model"
arms = ["baseline", "prompt_reminder", "skill_scaffold", "expert_oversight"]
lines = [
    f"# Multi-scaffold stability (tier2) — {model}",
    "",
    "| Arm | Status | erosion.tier2 pr | erosion.tier2 mean | extract_discipline pr |",
    "|-----|--------|------------------|--------------------|-----------------------|",
]
for arm in arms:
    p = out / f"{model}-{arm}.json"
    if not p.is_file():
        lines.append(f"| {arm} | MISSING | — | — | — |")
        continue
    d = json.loads(p.read_text())
    by = {g.get("metric_id"): g for g in (d.get("gates") or [])}
    t2 = by.get("erosion_indicator.tier2") or {}
    ex = by.get("extract_discipline") or {}
    lines.append(
        f"| {arm} | ok | {t2.get('pass_rate', '—')} | {t2.get('mean', '—')} | {ex.get('pass_rate', '—')} |"
    )
summary = out / "SUMMARY.md"
summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
print(f"Wrote {summary}")
PY

echo "TIER2_SCAFFOLD_DONE $(date -Is)" | tee -a "$LOG_DIR/run.log"
