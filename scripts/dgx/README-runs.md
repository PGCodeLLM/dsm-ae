# DGX benchmark runs (SWE-bench-Pro + NL2Repo-Bench x gpt-5.6-terra/luna)

Operator notes for reproducing the ~10% sample runs on the DGX box.
**No secrets in this file.** Credentials live in the gitignored `dgx.yaml`
(SSH) and `models.yaml` (model API key); both are read at runtime only.

## 0. TL;DR

```bash
# from the repo root, on the workstation
python3 scripts/dgx/build_sample_manifest.py     # -> reports/behaviour-task/sample-manifest.json
./scripts/dgx/dgx_ssh.sh 'echo ok'               # opens the multiplexed SSH master

# on the DGX (already done once; see sections below to rebuild)
~/dsm-dgx/make_configs.sh
~/dsm-dgx/launch_runs.sh

# back on the workstation, when runs finish
./scripts/dgx/pull_results.sh --all
```

## 1. The machine

`gx10-102d`, an **aarch64** NVIDIA GB10 (DGX Spark), Ubuntu 6.17 kernel,
3.6T disk (2.1T free), Docker 28.x, user in the `docker` group.
This is *not* the k8s cluster the reference bundles came from — there is no
evalhub, no opensandbox server running, and `/tasks` does not exist.

## 2. What produced the reference bundles

`evalhub-extract/*/config.json` shows the original harness was **Harbor**
(the CAIS/Terminal-Bench successor; `result.json` carries `task_name:
"cais/..."`, agent `opencode` 1.18.18 / `claude-code` 2.1.207) driven by an
internal Huawei "evalhub" k8s wrapper with an `opensandbox` environment and a
squid proxy at `squid.evalhub.svc.cluster.local:3128`.

None of that k8s machinery is reachable from the DGX. The reproduction here
drops the evalhub/opensandbox/squid layer entirely and runs **Harbor 0.22.0
with `environment.type: docker`**, which is exactly what the upstream adapter's
own `swebenchpro.yaml` does. The output layout is identical, which is what
`src/dsm_ae/harbor/` consumes.

## 3. Problems hit and how they were fixed

| # | Problem | Fix |
|---|---------|-----|
| 1 | Concurrent password SSH logins hung the session | `dgx_ssh.sh` uses `ControlMaster`/`ControlPersist` so all commands share one authenticated connection. Password is fed via `SSH_ASKPASS` (never in argv/logs). |
| 2 | Task images are **amd64**, DGX is **aarch64** → `exec format error` | `docker run --privileged --rm tonistiigi/binfmt --install amd64` registered `qemu-x86_64`. All runs export `DOCKER_DEFAULT_PLATFORM=linux/amd64`. |
| 3 | Reference config points at `squid.evalhub.svc.cluster.local` (k8s-internal, unresolvable) | Dropped. The DGX reaches the model endpoint directly over HTTPS; verified `/v1/models` = 200 and a real chat completion for both models. No proxy needed. |
| 4 | Harbor not installed | `uv venv ~/harbor-venv` + `uv pip install harbor==0.22.0`. |
| 5 | SWE-bench-Pro dataset absent (`/tasks` missing, not in the public Harbor registry) | Public adapter exists at `laude-institute/harbor:adapters/swebenchpro`; sparse-cloned and run with `--task-ids` to generate exactly the 70 sampled tasks from `ScaleAI/SWE-bench_Pro` on HuggingFace. |
| 6 | Adapter rejected every id (`Instance not found`) | Two causes: run-bundle dir names are **lowercased**, and I had stripped the `instance_` prefix. Canonical ids are used verbatim (`scripts/dgx/swebenchpro_instance_ids.txt`); the sampler asserts the canonical set matches the bundle universe case-insensitively. |
| 7 | Harbor `--dataset-path` does not exist; a dataset path must be a **parent dir of task dirs**, not one task | Configs point at `datasets/<bench>/`. Also: CLI flags like `-n` reset the parsed config, so the job is launched with `-c <config>` plus only timeout/env flags. |
| 8 | No public NL2Repo-Bench Harbor adapter | Reconstructed by `build_nl2repo_tasks.py` from two public sources — GHCR images `ghcr.io/multimodal-art-projection/nl2repobench/<name>:1.0` and the upstream repo's `test_files/<name>/{start.md,test_commands.json,test_case_count.txt}`. |
| 9 | NL2Repo images lack `start.md` (the requirements doc the task refers to) | The Dockerfile `COPY`s it into `/workspace/start.md`, matching the reference trajectories' first user turn. |
| 10 | NL2Repo verifier wrote reward to the wrong path | Harbor reads `/logs/verifier/reward.txt`, not `/logs/reward.txt`. Fixed; re-verified with the `nop` agent (0 exceptions, reward `0.000000`). |
| 11 | `AgentSetupTimeoutError` after 360 s | opencode's setup runs `apt-get install nodejs npm`, which is very slow under x86 emulation. Runs use `--agent-setup-timeout-multiplier 12`. |
| 12 | `more-Itertools` failed to build: *repository name must be lowercase* | The upstream `test_files/` dir keeps the package's original casing, but the published GHCR image is all-lowercase. The generator now lowercases the image ref only (the task dir name keeps upstream casing). Task regenerated; see "Known follow-up" below. |

### Known follow-up

`more-Itertools` failed early in **both** NL2Repo jobs (before the casing fix
landed). Its task definition is now correct, but the two running jobs still
hold the old plan. After the current jobs finish, re-run just that instance:

```bash
# on the DGX
mkdir -p ~/dsm-dgx/datasets/nl2repo-fixup
cp -r ~/dsm-dgx/datasets/nl2repobench/more-Itertools ~/dsm-dgx/datasets/nl2repo-fixup/
# then point a copy of configs/nl2repobench-{terra,luna}.yaml at that dir
# (change `jobs_dir` too so it lands beside the main run) and launch as usual.
```

The other 9 NL2Repo instances and all 70 SWE-bench-Pro instances are unaffected.

## 4. Sample selection

`scripts/dgx/build_sample_manifest.py` → `reports/behaviour-task/sample-manifest.json`
(seed 42, deterministic — re-running gives an identical file).

- **SWE-bench-Pro: 70 / 731 (9.6%)**, stratified by repo with largest-remainder
  apportionment so all 11 repos appear:
  ansible 9, internetarchive 9, flipt-io 8, qutebrowser 8, gravitational 7,
  future-architect 6, navidrome 6, protonmail 6, element-hq 5, nodebb 4, tutao 2.
  Languages: **Go 27, Python 26, TypeScript 13, JavaScript 4**.
- **NL2Repo-Bench: 10 / 104 (9.6%)**, all Python:
  deepdiff, flask-restful, graphneuralnetwork, mechanicalsoup, mootdx,
  more-Itertools, paillier, pyperclip, sklearn, stamina.

## 5. Layout on the DGX

```
~/dsm-dgx/
  .env.models                # OPENAI_API_KEY / OPENAI_BASE_URL, mode 600
  configs/{swebenchpro,nl2repobench}-{terra,luna}.yaml
  datasets/swebenchpro/      # 70 generated Harbor tasks
  datasets/nl2repobench/     # 10 generated Harbor tasks
  runs/                      # job output (pull these back)
  logs/                      # one log per job
  harbor-src/                # sparse clone of the swebenchpro adapter
~/harbor-venv/               # harbor 0.22.0
```

## 6. Validation done before launching

- `oracle` agent on one SWE-bench-Pro task → **reward 1.0** in 2m05s
  (proves image build + test harness + reward plumbing all work under emulation).
- `nop` agent on one NL2Repo task → **reward 0.000000**, 0 exceptions
  (proves the reconstructed verifier scores and writes correctly).

## 7. Pulling results back

```bash
./scripts/dgx/pull_results.sh            # list
./scripts/dgx/pull_results.sh --all      # fetch into evalhub-runs/
```

Output layout per trial is `<run>/<instance>/agent/trajectory.json`,
`verifier/reward.txt`, `result.json` — unchanged for `src/dsm_ae/harbor/`.
Note `opencode` sets `SUPPORTS_ATIF = True`, so `agent/trajectory.json` is
emitted in the same ATIF schema as the reference bundles.

## 8. Cost / rate limiting

`models.yaml` pins **rpm 6** for both models. Each job uses
`n_concurrent_trials: 2`, so at most 8 agents are in flight with all four jobs
running. Do not raise this without raising rpm.
