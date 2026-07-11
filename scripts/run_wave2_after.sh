#!/bin/bash
set -e
cd /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
# wait until first wave diagnose processes exit
while pgrep -f 'work/np_gpt55|work/np_gpt54mini|run_new_packs_grok' >/dev/null 2>&1; do
  sleep 30
done
export PYTHONUNBUFFERED=1
WAVE2="memory_context,handoff_mini,eval_gaming_mini,sandbag_mini,clarify_verify,pii_safety,nfr_omit"
for M in gpt-5.5 gpt-5.4-mini; do
  SAFE=$(echo $M | tr './' '_')
  echo "===== WAVE2 $M $(date -Is) =====" >> logs/wave2.log
  dsm-ae diagnose -m "$M" --models-yaml models.yaml -p "$WAVE2" --k 3 -j 2 --rpm 6 \
    --work-dir "work/w2_$SAFE" \
    --out "reports/new-packs/${M}-wave2.md" \
    --json "reports/new-packs/${M}-wave2.json" >> logs/wave2.log 2>&1 || echo FAIL $M >> logs/wave2.log
done
# grok wave2
DSM_AE_K=3 DSM_AE_CONCURRENCY=2 python3 - <<'PY' >> logs/wave2.log 2>&1
import json, os, sys
from pathlib import Path
sys.path.insert(0,"src")
os.chdir("/home/arcyleung/Projects/grok_trace_analysis/dsm-ae")
from dsm_ae.diagnose import diagnose
from dsm_ae.report import render_markdown
from dsm_ae.litellm_client import LiteLLMClient
from dsm_ae import litellm_client as lc, diagnose as dm
auth=json.loads(Path.home().joinpath(".grok/auth.json").read_text())
key=list(auth.values())[0]["key"]
client=LiteLLMClient(model="grok-build", api_base="https://cli-chat-proxy.grok.com/v1", api_key=key,
 extra={"timeout":120,"num_retries":2,"extra_headers":{"User-Agent":"grok/0.2.95","x-grok-client-version":"0.2.95","x-grok-client-surface":"cli"}})
lc.make_client=dm.make_client=lambda *a,**k: client
packs=["memory_context","handoff_mini","eval_gaming_mini","sandbag_mini","clarify_verify","pii_safety","nfr_omit"]
report=diagnose(model="grok-build", packs=packs, k=3, concurrency=2, work_dir=Path("work/w2_grok"))
Path("reports/new-packs/grok-build-wave2.md").write_text(render_markdown(report))
print("wave2 grok done")
PY
echo "WAVE2 COMPLETE $(date -Is)" >> logs/wave2.log
