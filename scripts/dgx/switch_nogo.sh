#!/usr/bin/env bash
# Switch the SWE-bench-Pro jobs onto the Go-free dataset.
#
# Go is not measurable on this aarch64 box: the Go runtime dies under
# qemu-x86_64 (lfstack / SIGSEGV) on a clean checkout with no agent involved,
# and every mitigation failed (GOMAXPROCS=1, asyncpreemptoff, GOGC=off). The
# trials do not fail cheaply -- the agent runs to completion (10-34 min) and
# only then does the verifier return tests_run=0, which HarborTrial.scoreable
# correctly refuses to score. ~34 such trials remain across both jobs, roughly
# 8h of the remaining 24h.
#
# Two properties matter here, both learned the hard way:
#
#   1. NO DEADLINE. An earlier version had a 2h cap after which it switched
#      regardless of drain state -- which would have killed live trials, the
#      exact thing the gate exists to prevent. This waits indefinitely.
#   2. Orphans are not counted as live. Harbor reaps a timed-out trial (writes
#      exception.txt) but leaves its environment container running at ~100%
#      CPU forever. Counting those as live would block the drain permanently.
#      A trial is live only if it has neither a reward nor an exception.
#
# Harbor skips trials already completed in the same jobs_dir, so all finished
# work is preserved across the relaunch.
set -uo pipefail

DSM=/home/bmc/dsm-dgx
log() { echo "$(date -u +%H:%M) $*"; }

live_trials() {
  local n=0 d base lower
  for d in "$DSM"/runs/swebenchpro-*/*/; do
    [ -d "$d" ] || continue
    [ -f "$d/verifier/reward.txt" ] && continue   # finished
    [ -f "$d/exception.txt" ] && continue         # reaped (container may orphan)
    base=$(basename "$d")
    lower=$(printf '%s' "$base" | tr '[:upper:]' '[:lower:]')
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -qi -- "$lower"; then
      n=$((n + 1))
    fi
  done
  printf '%s' "$n"
}

while :; do
  n=$(live_trials)
  if [ "$n" -eq 0 ]; then
    log "drained — no live swebenchpro trials"
    break
  fi
  log "$n live trial(s); waiting"
  sleep 300
done

log "stopping swebenchpro sessions"
tmux kill-session -t dsm-swebenchpro-terra 2>/dev/null || true
tmux kill-session -t dsm-swebenchpro-luna 2>/dev/null || true
sleep 3

log "repointing configs at swebenchpro-nogo"
sed -i 's|datasets/swebenchpro$|datasets/swebenchpro-nogo|' \
  "$DSM"/configs/swebenchpro-terra.yaml \
  "$DSM"/configs/swebenchpro-luna.yaml
grep -H 'path:.*swebenchpro' \
  "$DSM"/configs/swebenchpro-terra.yaml \
  "$DSM"/configs/swebenchpro-luna.yaml

log "relaunching on 43 non-Go tasks (concurrency 2)"
"$DSM"/launch_runs.sh swebenchpro-terra swebenchpro-luna
log "done"
tmux ls
