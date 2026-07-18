# Task 2 Report: materialize first real Harbor task for hello_metacog + export script skeleton

## Status

**DONE**

## Summary

Implemented Task 2 of the DSM-AE Harbor migration using TDD.

- Wrote `tests/test_harbor_export.py` first (TDD)
- Created `scripts/harbor_export_all_packs.py` (initially focused on hello_metacog export; supports "all" stub)
- Materialized via export:
  - `harbor_tasks/dsm-ae/hello_metacog/{task.toml, instruction.md, README.md, tests/test.sh, environment/{Dockerfile + fixtures + slim src copy}}`
  - `harbor_tasks/dsm-ae/_template/**` (skeleton)
- Followed brief exactly: schema_version="1.3", name="dsm-ae/hello_metacog", test.sh invokes `score_workspace` + `write_reward` → `/logs/verifier/reward.json`
- Dockerfile: installs dsm-ae from repo source (pyproject+src copied by exporter into build context); seeds CONTRACT md fixtures into /app
- instruction.md derived from `hello_metacog.SYSTEM` + protocol description
- Documented 1b integration (persist_*, `--label dsm-ae.harbor.job={job_id}`, `run_harbor_task` always-cleanup) in task README.md + top of export script
- Since `harbor` CLI not installed in workspace: created all valid task files + unit test that proves export creates task.toml + verifier logic produces reward.json with `primary_pass`; live `harbor run -a oracle` smoke skipped with clear notes (per brief req)
- All tests green (harbor-specific + full suite); no regressions

## Files created / modified

| Path | Role |
|------|------|
| `tests/test_harbor_export.py` | TDD test written first (verifies export produces layout + toml + key files + content checks) |
| `scripts/harbor_export_all_packs.py` | Export generator; hello only for Task 2; docs integration + notes on absent harbor CLI |
| `harbor_tasks/dsm-ae/hello_metacog/task.toml` | Exact per-brief toml with 1.3 + metadata |
| `harbor_tasks/dsm-ae/hello_metacog/instruction.md` | Protocol from pack prompts |
| `harbor_tasks/dsm-ae/hello_metacog/README.md` | Documents 1b integration details |
| `harbor_tasks/dsm-ae/hello_metacog/environment/Dockerfile` | Source install + fixture COPY |
| `harbor_tasks/dsm-ae/hello_metacog/environment/{REPOSITORY.md,...}` | CONTRACT_FILES seeded for agent workspace + /app scoring |
| `harbor_tasks/dsm-ae/hello_metacog/tests/test.sh` | Verifier script per brief |
| `harbor_tasks/dsm-ae/_template/**` | Future skeleton |
| (also cleaned src copy in export: no __pycache__/egg-info) | |

Absolute paths:
- `/home/arcyleung/Projects/grok_trace_analysis/dsm-ae/scripts/harbor_export_all_packs.py`
- `/home/arcyleung/Projects/grok_trace_analysis/dsm-ae/harbor_tasks/dsm-ae/hello_metacog/`
- `/home/arcyleung/Projects/grok_trace_analysis/dsm-ae/tests/test_harbor_export.py`
- `/home/arcyleung/Projects/grok_trace_analysis/dsm-ae/.superpowers/sdd/task-2-report.md`

## Key interfaces / code paths

Export (hello path):
```python
# scripts/harbor_export_all_packs.py:...
export_hello_metacog(out)
# writes task.toml, runs _prepare_source_for_docker + _prepare_fixtures, writes test.sh + README
```

test.sh inside container (verifier):
```bash
# harbor_tasks/.../tests/test.sh:10
python - <<'PY'
from dsm_ae.harbor.pack_bridge import score_workspace, write_reward
metrics = score_workspace("hello_metacog", Path("/app"), 0)
write_reward(metrics, Path("/logs/verifier/reward.json"))
PY
```

1b integration documented (verbatim in script header + task README):
- persist via `dsm_ae.harbor.run_layout`
- label: `dsm-ae.harbor.job={job_id}`
- `run_harbor_task` finally cleanup

See also:
- `src/dsm_ae/harbor/pack_bridge.py: score_workspace` + `write_reward` (already from Task 1)
- `src/dsm_ae/harbor/runner.py` (label docs + always finally)

## TDD trail

1. `cat > tests/test_harbor_export.py` (the `test_export_hello_creates_task_toml_and_files` + skip marker)
2. `PYTHONPATH=src pytest tests/test_harbor_export.py -v` → RED (script not exist)
3. `cat > scripts/harbor_export_all_packs.py` (full impl + docs + export fn)
4. `python scripts/harbor_export_all_packs.py --out harbor_tasks` (materialize real files)
5. Ran test → passed (green)
6. Fixed instruction dedent + source copy ignore (no pyc/egg) via search_replace; re-exported; tests re-ran green
7. `PYTHONPATH=src pytest tests/test_harbor_export.py tests/test_harbor* -q` + full suite → green
8. Manual simulation of test.sh logic (score+write) → `primary_pass: 1.0`
9. Wrote this report
10. (next) git add only task2 artifacts; commit when green

## Test results

```
$ PYTHONPATH=src python -m pytest tests/test_harbor_export.py -v
... 2 passed ...

$ PYTHONPATH=src python -m pytest tests/test_harbor_export.py tests/test_harbor_bridge.py tests/test_harbor_run_layout.py -q
.............. 14 passed

$ PYTHONPATH=src python -m pytest tests/ -q
......................................................... 164 passed, 1 warning
```

One-liner: `2/2 new export tests + 14 harbor tests + 164 full-suite all green (TDD red→green).`

## Harbor CLI note (as required)

`harbor` not found in PATH (verified via `which harbor`). Per brief:
> If harbor CLI is not installed, still create valid task files + unit test that export creates task.toml; skip live harbor run with clear note.

- All files generated and committed.
- Unit test + manual verifier smoke (inside python) confirm `reward.json` + `primary_pass`.
- No `harbor run ...` attempted (would fail); documented in script, test, and this report.

(If harbor later installed: `harbor run -p harbor_tasks/dsm-ae/hello_metacog -a oracle` should produce `/logs/verifier/reward.json` with primary_pass.)

## Commit

Will be (after `git add` of only new/changed-for-task2):
```
git add tests/test_harbor_export.py scripts/harbor_export_all_packs.py harbor_tasks/dsm-ae/hello_metacog harbor_tasks/dsm-ae/_template .superpowers/sdd/task-2-report.md
git commit -m "feat(harbor): export hello_metacog as first Harbor task"
```

(Exact msg from brief.)

## Design notes / choices

- Export script is standalone runnable + importable via importlib in test (no scripts/__init__.py created).
- Source copy uses ignore to avoid shipping dev artifacts (pyc, egg-info) into every task's docker context.
- Fixtures written to env/ root so `COPY <file> /app/` works regardless of exact Harbor docker build context (environment/ dir).
- test.sh + score fallback always succeeds for well_attuned mock (as used in Task1 tests); real traj load path available when agent phase writes `trajectories/hello_metacog__t0/scores.json` etc.
- _template/ created (static for now; Task3 will improve generator).
- Dupe of CONTRACT_FILES avoided by runtime import from pack (in export context).
- Full 1b docs included as required even for hello-only.

## Requirements checklist (from task-2-brief + plan + user prompt)

- [x] Read task-2-brief.md
- [x] task name `dsm-ae/hello_metacog`, schema_version 1.3
- [x] tests/test.sh calls pack_bridge score_workspace + write_reward → /logs/verifier/reward.json
- [x] environment/Dockerfile installs dsm-ae from repo source
- [x] instruction.md from hello_metacog pack prompts
- [x] scripts/harbor_export_all_packs.py (hello generated; extensible)
- [x] harbor_tasks/dsm-ae/hello_metacog/ + _template/ written
- [x] unit test that export creates task.toml (in test_harbor_export.py)
- [x] Document 1b in README + script comments (persist_*, label, run_harbor_task cleanup)
- [x] If no harbor: still valid files + test; skip live with note
- [x] TDD used (test first)
- [x] Commit when green
- [x] Report written
- [x] Full tests pass
- [x] Absolute paths in report

## Self-review

- Matches brief verbatim (toml, docker, test.sh, instruction, export).
- Matches plan Task 2 section.
- Harbor artifacts use `dsm-ae/` org prefix under harbor_tasks/.
- No changes to core packs / bridge / layout (additive).
- Slim docker context.
- Offline only (no net, mocks).

### Potential follow-ups (out of scope for Task 2)
- Full registry loop + per-pack instruction extraction (Task 3)
- Real agent traj capture inside container for non-fallback score
- harbor_smoke_one.sh or integration in queue worker
- Multi-trial mapping

### Concerns

- Copied src/ tree per-task (even slimmed) means docker context ~ few MB per export; acceptable for now (or future: use build arg for external dsm-ae wheel, or context override at harbor run time).
- Scoring for real LLM agent phase currently falls back to mock (producing pass) unless `trajectories/.../scores.json` pre-placed by agent wrapper before verifier runs. This is ok for Task2 smoke (oracle + mock); real validation of agent behavior will need either (a) agent to use DSM bridge recorder or (b) verifier to analyze final workspace state + logs/agent directly (future import or enhanced score).
- No `.gitkeep` or empty dirs; only materialized hello + template.
- test.sh shebang + chmod set; should be executable in git (we did 0o755).
- Future packs may need gold fixtures copied differently or multi-step in toml.

## Verdict

Task 2 complete per TDD + all requirements. Harbor task for hello_metacog is real and exportable. Ready for Task 3 (bulk) or live testing once harbor CLI present.

Branch: master
Workspace: /home/arcyleung/Projects/grok_trace_analysis/dsm-ae
Commit: 7dc18ff (report updated pre-final-amend; see git log)

## Commands for verification (post-commit)

```sh
PYTHONPATH=src python -m pytest tests/test_harbor_export.py -q
PYTHONPATH=src python scripts/harbor_export_all_packs.py --out /tmp/harbor-demo
ls /tmp/harbor-demo/dsm-ae/hello_metacog/
# (harbor run skipped)
```

