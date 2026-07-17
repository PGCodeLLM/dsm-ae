#!/usr/bin/env bash
set -uo pipefail
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
export PYTHONUNBUFFERED=1
LOG=logs/backfill_pangu.log
mkdir -p logs reports/backfill work/backfill
log() { echo "$(date -Is) $*" | tee -a "$LOG"; }

log "probing pangu via chat completions"
python3 - <<'PY'
import time, yaml, urllib.request, json
from pathlib import Path
cfg=yaml.safe_load(Path('models.yaml').read_text())
entry=next(m for m in cfg['model_list'] if m['model_name']=='Beta_pangu_92b')
base=entry['litellm_params']['api_base'].rstrip('/')
key=entry['litellm_params']['api_key']
body=json.dumps({"model":"Beta_pangu_92b","messages":[{"role":"user","content":"ping"}],"max_tokens":3}).encode()
for i in range(60):
    try:
        req=urllib.request.Request(base+'/chat/completions', data=body,
            headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'})
        with urllib.request.urlopen(req, timeout=60) as r:
            if r.status==200:
                print('pangu up via chat', flush=True)
                break
    except Exception as e:
        print(f'pangu down ({e}); sleep 30', flush=True)
        time.sleep(30)
else:
    raise SystemExit('pangu never came up')
PY

run_one() {
  local model="$1" packs="$2"
  local safe; safe=$(echo "$model" | tr './' '_')
  log "START $model packs=$packs"
  dsm-ae diagnose -m "$model" --models-yaml models.yaml \
    -p "$packs" --k 10 -j 1 --rpm 4 \
    --work-dir "work/backfill/${safe}" \
    --out "reports/backfill/${safe}.md" \
    --json "reports/backfill/${safe}.json" \
    >>"$LOG" 2>&1
  log "DONE $model rc=$?"
}

run_one Beta_pangu_92b slop_indicator || true
run_one Beta_pangu_505b "slop_indicator,tool_integrity_tier2" || true
log "PANGU BACKFILL COMPLETE"
