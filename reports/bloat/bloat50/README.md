# Bloated context — 50% stage (v2 · clean k10 comparison)

**Condition:** `bloat50` (level=0.5)  
**Windows:** Codex operational (gpt-5.5=272k, gpt-5.6-*=372k) — see `reports/backfill/CONTEXT_WINDOWS.md`

## Comparison policy (fair baseline)

**Baseline columns** use **only** `reports/repro-shared/{model}/**/trial_*.json` (k=10 mini-testbeds).

They do **not** pool suite / queue / root historic runs (that dilution made bloat look artificially better).

Rebuild:

```bash
PYTHONPATH=src python3 scripts/rescore_sycophancy_offline.py   # fixed sycophancy scorer
PYTHONPATH=src python3 scripts/build_bloat_comparison.py \
  --models gpt-5.5,gpt-5.6-sol,gpt-5.6-terra,gpt-5.6-luna \
  --baseline-mode repro_k10
```

Artifacts:
- `baseline_k10/{model}.json` — assembled clean k=10 baseline
- `{model}.json` — bloat50 assembly from work checkpoints
- `comparison.html` — Comparison → Context Bloat tab
- `archive/comparison.polluted_pool.*.html` — old polluted multi-pool comparison (archived)

## OASD priming control

```bash
PYTHONPATH=src python3 scripts/run_oasd_priming_control.py --model gpt-5.5 --k 3
```

Writes `reports/bloat/priming_control/SUMMARY.md` (empty vs lorem50 vs traj50).
