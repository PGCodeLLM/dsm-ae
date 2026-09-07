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
| 13 | NL2Repo agent setup died: `apt-get update` → `404 Not Found` / *"does not have a Release file"* | The upstream images pin **Debian buster (10) / bullseye (11)**, both archived. Harbor's opencode `install()` calls `ensure_system_dependencies(curl, bash, coreutils, nodejs, npm)`; the images ship curl/bash/stdbuf but **no node/npm**, so it fell through to `apt-get install -y ... nodejs npm` against dead mirrors. Fixed in the generator's Dockerfile (`build_nl2repo_tasks.py`): (a) archived suites are repointed at `archive.debian.org` with `Acquire::Check-Valid-Until "false"`, and (b) a **pinned, sha256-checksummed Node v22.23.2 tarball** is unpacked into `/usr/local`, which makes Harbor's dependency check short-circuit so apt is never invoked at all. |

### Repair run (2026-09-07)

7 of the 20 NL2Repo trials and 3 of the SWE-bench-Pro trials raised exceptions.
Three distinct causes:

1. **Archived Debian apt repos** (problem 13 above) — `deepdiff` and
   `flask-restful`, in both jobs. Genuine setup failures; fixed in the
   generator and re-run.
2. **`more-Itertools` image-ref casing** (problem 12 above) — both jobs held
   the pre-fix plan. Re-run.
3. **Model-side 429 `model_cooldown`** — `mechanicalsoup` (terra) plus all
   three SWE-bench-Pro exceptions
   (`instance_gravitational__teleport__{iZwFoLH,bq6dyKb}`,
   `instance_tutao__tutanota-5181821__DD4qHmQ`). opencode's *run* phase, not
   setup: the endpoint returned
   `All credentials for model gpt-5.6-{terra,luna} are cooling down via
   provider codex` (HTTP 429, ~2.5 h reset). Each `agent/opencode.txt` holds
   exactly one event, that error. These are **not** environment bugs and need
   no code fix — they need re-running once the credential pool is warm, at
   rpm 6. All three SWE-bench-Pro ones already carry `reward.txt=0`, so they
   are scoreable but agent-less (no `trajectory.json`).

The repair run for causes 1 and 2 uses a separate dataset and jobs dir so the
main jobs are untouched:

```bash
# on the DGX
python3 ~/dsm-dgx/build_nl2repo_tasks.py \
  --out ~/dsm-dgx/datasets/nl2repo-fixup \
  --instances deepdiff flask-restful more-Itertools
# configs/nl2repobench-fixup-{terra,luna}.yaml -> jobs_dir ~/dsm-dgx/runs-fixup
tmux new-session -d -s dsm-nl2repobench-fixup-terra "harbor run -c ~/dsm-dgx/configs/nl2repobench-fixup-terra.yaml ..."
```

Concurrency stays at `n_concurrent_trials: 2` per job to respect rpm 6.
The output layout under `runs-fixup/` is identical, so
`src/dsm_ae/harbor/adapter.py` reads it unchanged.

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

## 9. OPEN ISSUE: SWE-bench-Pro rewards are not yet trustworthy

**Status: under investigation. Do NOT report the current SWE-bench-Pro zeros
as model performance.**

The first SWE-bench-Pro rewards came back 6/6 zero. Investigating rather than
accepting them turned up **two independent infrastructure artifacts**, plus a
strong control that proves they are artifacts:

**Control.** The reference bundles (same tasks, real x86 harness) score
navidrome 0.526, gravitational 0.583, tutao 0.700. Getting 0.000 on those exact
repos is not a plausible model result -- it is our environment.

### Artifact A -- Go verifiers produce zero test results (root cause pending)
The four Go trials (navidrome, gravitational) all wrote `reward=0` with
`verifier/output.json == {"tests": []}` -- **zero tests ran**, so those rewards
measured nothing.

Two false leads were chased and are recorded here so they are not repeated:

1. *"Go's GC crashes under QEMU."* The navidrome verifier log does contain
   `fatal error: lfstack` from inside the Go runtime, which looked like a
   known QEMU multi-threaded-GC defect. Real, but not established as the cause.
2. *"The Go images cannot exec under emulation."* `docker run ... <img>
   /bin/sh` returns `cannot execute binary file`. This turned out to be a
   **probe artifact, not a defect**: in the same image `/usr/bin/bash`,
   `/bin/bash` and the explicit loader all run fine and print `x86_64`, and
   `go version` reports `go1.24.3 linux/amd64`. The ansible image -- whose
   trial produced a perfectly good result -- fails the identical `/bin/sh`
   probe. So `/bin/sh` says nothing about whether a task works.

**ROOT CAUSE CONFIRMED.** The Go images are valid amd64 (ELF `3e 00`), contain
the x86-64 loader, and `go version` reports `go1.24.3 linux/amd64` -- the
toolchain itself is fine. But running the task's own test target on a **clean
checkout with no agent involved** reproduces the crash deterministically:

```
cd /app && go test -tags netgo -run TestPersistence ./persistence/...
  default GOMAXPROCS   -> fatal error: lfstack
  GOMAXPROCS=1 -p 1    -> fatal error: lfstack
```

So the Go runtime's lock-free stack corrupts under `qemu-x86_64` regardless of
parallelism. **Serialising does not help**, which rules out the obvious
multi-threaded-GC mitigation. This is an emulator/runtime incompatibility, not
anything the model or the harness did. It is fully reproducible in one command,
which makes it easy to re-check on a different host or QEMU version.

**All mitigations tried have FAILED:**

| setting | result |
|---|---|
| default | `fatal error: lfstack` |
| `GOMAXPROCS=1 -p 1` | `fatal error: lfstack` |
| `GODEBUG=asyncpreemptoff=1` | `fatal error: lfstack` |
| `GOGC=off` | `SIGSEGV` |
| `GODEBUG=asyncpreemptoff=1 GOGC=off` | `SIGSEGV` |

Serialising, disabling async preemption, and disabling the GC all fail, so this
is not a tunable-parameter problem. **Conclusion: Go tests are not runnable
under qemu-x86_64 on this aarch64 box.** The 27 Go instances (39% of the
SWE-bench-Pro sample: flipt-io 8, gravitational 7, future-architect 6,
navidrome 6) cannot be measured on this hardware.

### Required decision (needs a human)

1. **Run the Go subset on a real x86_64 host.** Only option that yields the
   full stratified sample the study was designed around. Everything needed is
   reproducible: `build_sample_manifest.py` (seed 42) plus the swebenchpro
   adapter regenerate the identical 27 tasks anywhere.
2. **Report Python/TypeScript/JavaScript only**, stating explicitly that Go was
   not measurable on this hardware. Honest, but it removes the Go arm and
   weakens the language-vs-agentic comparison, since Go is the largest
   non-Python stratum.

Do **not** silently report the Go zeros. `triage_rewards.py` marks them
`ARTIFACT_NO_TESTS_RAN` and excludes them from per-language rates specifically
so this cannot happen by accident.

**Cost note (matters for the decision).** Go trials are *not* cheap. The agent
runs to completion first and only then does the verifier fail:

```
gravitational  agent_execution 23:53:51 -> 00:03:47  (~10 min), verifier 16s
navidrome      agent_execution 22:46:54 -> 23:21:06  (~34 min), verifier 13s
```

So each Go trial spends real model tokens producing a patch that can never be
scored. Across 27 Go instances x 2 models = 54 trials, that is a substantial
amount of spend on unmeasurable results.

Given rpm=6, those trials also occupy scarce request budget that the
measurable Python/TS/JS trials could use. If the decision is to defer Go to
real x86 hardware, the cheapest action is to **restart the two SWE-bench-Pro
jobs against a Go-free dataset directory** (the 43 non-Go tasks), rather than
let the current jobs work through all 27 Go instances twice. The NL2Repo jobs
are unaffected and should be left alone.

### Artifact B -- tutao (TypeScript) reward is mis-scored
The tutao trials **passed** their tests, but scored 0. The task's expected test
name embeds an assertion count that changes with the code:

```
required: 'test/api/Suite.ts | api tests (3029 assertions)'
observed: 'test/api/Suite.ts | api tests (882 assertions)'  PASSED
          'test/api/Suite.ts | api tests (223 assertions)'  PASSED
```

Exact-name matching cannot succeed here. This is **not** an inherent grader
bug: on the reference (real x86) harness **14/20 tutao instances scored > 0**,
so the same grader works there. Our environment produces a *different test
partitioning* (882 + 223 assertions instead of one 3029-assertion run), most
likely because the suite shards by timing/CPU and emulation changes that.

**Scope: 1 task out of 43 non-Go tasks.** Scanning every sampled task's
`tests/config.json` for expected names containing an assertion count:

```
tutao 1/2   element-hq 0/5   protonmail 0/6   nodebb 0/4
ansible 0/9   internetarchive 0/9   qutebrowser 0/8
```

Only `instance_tutao__tutanota-5181821...` is affected -- and it happens to be
the one task both TypeScript trials so far have run, which is why TS currently
shows a misleading 0.000. **TypeScript as a language is fine**; the other 12
TS/JS tasks use ordinary test names. `triage_rewards.py` now detects this task
and marks such trials `ARTIFACT_GRADER_NAME_MISMATCH`, so it is excluded
automatically rather than remembered.

### Mistake made during debugging (fixed)
While probing, a bind-mount created an empty directory at
`/usr/bin/qemu-x86_64` on the host, clobbering the binfmt interpreter path.
The `F` (fix-binary) flag kept a cached fd alive so existing runs were not
disturbed, but new containers mounting that path broke. Removed the stray
directory and reinstalled the real qemu binary (8.1 MB, from
`tonistiigi/binfmt`) at that path; `alpine` amd64 exec re-verified. The four
production jobs were checked before and after and were unaffected
(10 processes, 8 env containers, same reward counts).

### What must NOT happen
Reporting emulator-induced zeros as "the model is weak at Go", or grader-induced
zeros as "weak at TypeScript", would fabricate exactly the language-deficit
conclusion this study exists to distinguish from genuine agentic deficits.
Quarantine SWE-bench-Pro rewards until A and B are resolved.

NL2Repo-Bench (Python) is unaffected and is producing well-spread, plausible
rewards (0.98, 1.0, 0.0).

### Prepared, but NOT activated (awaiting the decision above)

`~/dsm-dgx/datasets/swebenchpro-nogo/` is staged on the DGX: symlinks to the
**43 non-Go tasks** (ansible 9, internetarchive 9, qutebrowser 8, protonmail 6,
element-hq 5, nodebb 4, tutao 2). Nothing points at it yet -- the four original
jobs are still running unchanged.

To switch the SWE-bench-Pro jobs onto it (only if option 2 is chosen):

```bash
tmux kill-session -t dsm-swebenchpro-terra
tmux kill-session -t dsm-swebenchpro-luna
sed -i 's|datasets/swebenchpro$|datasets/swebenchpro-nogo|' \
  ~/dsm-dgx/configs/swebenchpro-terra.yaml ~/dsm-dgx/configs/swebenchpro-luna.yaml
~/dsm-dgx/launch_runs.sh swebenchpro-terra swebenchpro-luna
```

Harbor skips trials it has already completed in the same `jobs_dir`, so the
finished Python/TS/JS trials are preserved.

### DECISION (2026-09-07): switch to `swebenchpro-nogo`, drain first

Option 2 chosen. Go is **not measurable on this hardware** and the failure is
not a tunable: the Go runtime dies under `qemu-x86_64` on aarch64 with
`fatal error: lfstack` (or SIGSEGV) on a clean checkout with no agent
involved, and every mitigation failed — `GOMAXPROCS=1 -p 1`,
`GODEBUG=asyncpreemptoff=1`, `GOGC=off`, and combinations.

The deciding factor was cost, not principle. Go trials do **not** fail
cheaply: the agent runs to completion first (gravitational ~10 min,
navidrome ~34 min) and only then does the verifier fail in ~15s with
`tests_run=0`. That is 27 Go instances x 2 models = **54 trials** paying full
token cost for rewards that `HarborTrial.scoreable` correctly refuses to
score, while consuming rpm=6 budget the measurable strata need.

Executed as `~/dsm-dgx/switch_nogo.sh` in tmux `nogo-switch` rather than
immediately: it polls until no `instance_*` containers remain (2h cap), then
kills and relaunches the two SWE-bench-Pro jobs against
`datasets/swebenchpro-nogo`. Restarting mid-trial would have discarded up to
an hour of already-paid agent work on four non-Go trials that survive the
switch anyway. Harbor skips completed trials in the same `jobs_dir`.

**Consequence for the study, stated plainly:** the SWE-bench-Pro arm on this
box covers Python / TypeScript / JavaScript only. Go is the largest non-Python
stratum in the sample (27 of 70), so its absence is a real limitation, not a
rounding error — the matched-triad composite fixture (`fixtures/composite/`)
carries the Go arm instead, where the toolchain runs natively. Reproducing the
Go SWE-bench-Pro subset requires real x86_64 hardware; seed 42 makes the
selection reproducible anywhere.

**TypeScript is provisional too.** `tutao` suffers a grader mismatch where the
suite passes but scores 0 because the expected test name embeds an assertion
count that shifts with the code. The reference harness does not show this.
Unlike "zero tests ran", "passed but mis-scored" has no clean structural
signature, so it is detected but not auto-excluded.

### Commit-attribution note (2026-09-07)

`scripts/dgx/build_nl2repo_tasks.py`, `triage_rewards.py`, and parts of this
README were authored by the NL2Repo-repair and triage workstreams but were
swept into commits `a107e6f` ("fix(task-layer): exclude trials where the
verifier ran zero tests") and `a208107` ("docs(dgx): record no-Go decision")
by a `git add -A scripts/dgx/` in a concurrent workstream. Those commit
messages do **not** describe the apt/Node repair or the triage classifier.
The content landed intact and is verified; history is left unrewritten
because the commits are already the shared base for later work. This note is
the correction of record.

### Problem 14: model-side 429 credential cooldown (not an environment bug)

Four trials died in opencode's **run** phase (not setup) with a ~1KB
`agent/opencode.txt` containing a single event: `All credentials for model
gpt-5.6-{terra,luna} are cooling down via provider codex`, HTTP 429,
`reset_seconds` ~7800-8800. Affected: `mechanicalsoup__qvyiCUS`,
`instance_tutao__tutanota-5181821__DD4qHmQ`,
`instance_gravitational__teleport__{bq6dyKb,iZwFoLH}`.

Scope check: **15 of 18** trials show cooldown text at least once, but only
those 4 died of it — the rest retried through. Live trials were confirmed
still streaming (opencode.txt at 100KB/43KB, updated within the minute), so
the cooldown is transient backpressure, not an outage. Nothing to fix in
code; these need re-running when the credential pool is warm.

Note for trajectory analysis: the two `gravitational` trials and the `tutao`
one have `reward.txt=0` but **no `trajectory.json`**, so they are useless for
behaviour scoring even though they look scoreable by reward alone. Any
re-run intended to feed `map_behaviour_to_task.py` must produce a trajectory,
not just a reward.

## 10. Observed: occasional per-trial agent stall (self-limiting, no action needed)

One trial (`instance_protonmail__webclients__cENF6s2`, luna) sat at ~4% CPU
with a **0-byte `agent/opencode.txt` for 73 minutes**. Diagnosis:

- `opencode` process alive, but its log stops after "project copy refresh done"
  and never reaches a `message=stream` line -- i.e. it never issued a model call.
- **Not rate limiting**: no 429/retry/timeout signals in the opencode log.
- **Not systemic**: the sibling protonmail trial on the *other* model was
  actively streaming at the same moment, and both jobs show healthy stream
  counts across trials (luna 1-34, terra 7-37 per trial).

So it is an isolated per-trial hang, not a model, endpoint, or rpm problem.

**It is self-limiting and needs no intervention:** the task's `timeout_sec =
3000` with `--agent-timeout-multiplier 2` gives a hard 6000s (100 min) cap, so
Harbor kills it ~01:55, and `--max-retries 1` grants one more attempt. Watch
for `AgentTimeoutError` in the job log to confirm the cap fired.

If stalls become frequent (say >10% of trials), that would change the picture
and warrant investigating opencode's startup path under emulation -- but a
single occurrence is expected noise at this concurrency.


### Problem 15: orphaned container survives Harbor's own trial reap

`instance_protonmail__webclients__cENF6s2` (luna) hit
`AgentTimeoutError: Agent execution timed out after 6000.0 seconds`. Harbor
reaped the *trial* correctly at 01:55 — `exception.txt` written, verifier
directory created, no `reward.txt` — but the **environment container was left
running**, still burning 103% CPU and 2.4GB an hour later.

The tell that distinguishes this from a live-but-slow trial: `agent/opencode.txt`
frozen at **0 bytes** while the container shows high CPU. A working trial's
opencode.txt grows steadily (the healthy siblings were at 142KB and 182KB,
touched within the minute). High CPU alone is not evidence of progress.

Why it mattered here beyond wasted compute: `switch_nogo.sh` gates on
`docker ps | grep instance` reaching zero before switching datasets. An
orphan that never exits blocks that drain **indefinitely** — the switch would
have sat until its 2h deadline and then fired mid-trial anyway, which is
exactly what the drain gate exists to avoid.

Resolved with `docker rm -f` on that one container after confirming from
`exception.txt` that the trial was already dead. Harbor's `--max-retries 1`
grants the instance another attempt.

**Check to run before trusting a drain gate:** cross-reference container
liveness against agent-log growth, not container status. A container in
`docker ps` is not proof a trial is alive.

## 11. IMPORTANT: exceptions live in result.json, not trial.log

A third failure class was missed for several hours because I was grepping
`trial.log`. **Harbor records trial-level failures in
`result.json -> exception_info`**, and a trial can fail there while `trial.log`
looks unremarkable. Any health check that greps only `trial.log` will silently
under-report failures. `triage_rewards.py` now reads `result.json`.

Census once that was fixed (34 trials so far):

```
ARTIFACT_APT_404                8   agent's install step 404s -> agent never runs
GENUINE_PASS                    8
INCOMPLETE                      6   still running
ARTIFACT_AGENT_SETUP_FAILED     4   other non-zero exit during setup
ARTIFACT_RuntimeError           2   the more-Itertools image-casing bug (fixed)
ARTIFACT_NO_TESTS_RAN           2   Go / qemu
ARTIFACT_AGENT_TIMEOUT          1   the 100-min stall, reaped as predicted
GENUINE_FAIL                    1
ARTIFACT_GRADER_NAME_MISMATCH   1
```

**18 quarantined vs 9 trustworthy.** Earlier per-language means in this file
were computed before APT_404/setup failures were detected and were therefore
too optimistic in their denominators; the current script supersedes them.

### Artifact C -- apt 404 on Debian 11 images (FIXABLE)

`opencode`'s setup runs `apt-get update && apt-get install -y curl bash
coreutils nodejs npm`. Several NL2Repo images are **Debian 11 (bullseye)**,
which is EOL and has moved to `archive.debian.org`, so the install dies with
`404 Not Found` and exit 100 -- **before the agent makes a single model call**.

Affected so far: deepdiff, flask-restful, graphneuralnetwork, pyperclip
(4 instances x 2 models = 8 trials).

**First attempted fix FAILED** (recorded so it is not retried): rewriting all
three sources to `archive.debian.org` still exits 100, because
`archive.debian.org` does **not** carry a `debian-security` suite for bullseye:

```
Ign:2 http://archive.debian.org/debian-security bullseye-security InRelease
E: The repository 'http://archive.debian.org/debian-security bullseye-security
   Release' does not have a Release file.
```

**Fix v2 VERIFIED WORKING** (tmux `apttest3`): point the main suites at the
archive **and delete the security lines**, which no longer exist anywhere for an
EOL release. Result: `exit=0`, `Setting up nodejs`, `node v12.22.12`,
`npm 7.5.2` -- i.e. the exact command that was failing now succeeds:

```dockerfile
RUN sed -i -e '/debian-security/d' -e '/security.debian.org/d' \
           -e 's|deb.debian.org/debian|archive.debian.org/debian|g' /etc/apt/sources.list \
 && printf 'Acquire::Check-Valid-Until "false";\n' > /etc/apt/apt.conf.d/99no-check-valid
```

Note on method: the *first* version of this test reported `exit=0` for the
"before" case -- it never reproduced the bug, because `>/dev/null 2>&1`
swallowed the real exit status. A test that cannot reproduce the failure cannot
validate the fix. The corrected test reproduces it (`exit=100`, 9 x 404) and is
what these results come from.

Unlike the Go problem this is a genuine environment fix, not a workaround that
changes what is measured: it only lets the agent's own install step succeed.

### Artifact D -- upstream model quota exhaustion (429 cooling down)

Four trials died with opencode exiting 1 after the endpoint returned **HTTP
429**:

```
"All credentials for model gpt-5.6-terra are cooling down via provider codex"
reset_seconds: 8776   (~2h26m)
```

This is **not** our rpm setting and not something a retry solves quickly -- it
is the upstream provider behind the gateway exhausting its credentials, with a
multi-hour cooldown. Three of the four fired at the *same minute* (00:03), i.e.
a thundering herd from 8 concurrent agents starting work together.

Both models responded 200 again on a later manual probe, so the cooldown
clears -- but any trial in flight when it hits is lost, and it will recur.

**Update -- this was a startup burst, not an ongoing bleed.** The count has
stayed at 4 with **zero new 429s in the following hour**, and the endpoint
probes 200. All four hit within ~16 minutes of the jobs starting, when 8 agents
began work simultaneously; once trials desynchronised the pressure disappeared.

So lowering concurrency is **optional, not urgent**. If you want to reduce the
risk of losing trials to a future cooldown, drop `n_concurrent_trials` 2 -> 1
(4 agents instead of 8) and stagger job starts -- wall-clock cost is modest
since emulation is usually the bottleneck. But restarting the running jobs to
achieve this would cost more than it saves right now.

Note `--max-retries 1` does retry these, but a retry that starts inside a
2.4-hour cooldown just fails again, so retries are not a real mitigation here.


### Apt fix: VERIFIED by outcome (2026-09-07 02:23)

The `archive.debian.org` + pinned-Node repair is confirmed working, not merely
"built without error". In `runs-fixup`:

```
flask-restful__6KAohgZ = 1.000000
flask-restful__VDLzPdk = 1.000000
flask-restful__3gjirmY = 0.000000   (nop-agent control, correctly 0)
```

`flask-restful` is a Debian 10 buster image and was one of the 8 instances
that previously died at agent setup with apt 404s before making a single model
call. Two real agent trials now reach the verifier and **solve the task**.
That is outcome-level proof: the environment fix restored measurability
without changing what is being measured.

Diagnosis was independently corroborated two ways: the image's `sources.list`
points at `deb.debian.org` for `bullseye`/`bullseye-security` (EOL, archived),
and the 8 failures are spread across ~2.5h (23:21 → 01:35) rather than
clustered — systematic, not a transient mirror outage.

### Concurrency lowered 2 -> 1 (2026-09-07 02:19)

Applied to all 7 configs. 12 trials had died with `NonZeroAgentExitCodeError`,
predominantly HTTP 429 `credentials cooling down via provider codex` with
~2.4h resets — three firing in the same minute from 8 concurrent agents. That
is upstream provider capacity, **not** our `rpm: 6` setting, so the fix is
fewer simultaneous agents rather than slower request pacing.

Deliberately not applied by restarting: running jobs keep their old value
until the `nogo-switch` relaunch picks up the new configs, so no in-flight
trial is killed to apply a throughput tweak.

**Label precision matters here.** These 429 deaths occur *mid-run*, not during
setup, and were initially mislabelled `ARTIFACT_AGENT_SETUP_FAILED`. They are
now `ARTIFACT_MODEL_QUOTA_429`. The two route to different owners: apt 404 is
ours to fix, quota exhaustion is the gateway's capacity.

### Apt fix v2 is unnecessary — the Node pin already bypasses apt entirely

A follow-up investigation found that `archive.debian.org` carries **no
`debian-security` suite for bullseye**, so rewriting that line to the archive
host still 404s and the security line must be *deleted*, not rewritten. That
finding is correct in isolation, and would matter for any image that reaches
apt.

**No image in this run does.** Measured across all 7 fixup trials
(`runs-fixup`), covering buster *and* bullseye bases:

```
deepdiff__fFcGCAa       reward=-         exc=no  apt_errs=0
deepdiff__sCBxcoN       reward=-         exc=no  apt_errs=0
more-Itertools__K2x9T4G reward=-         exc=no  apt_errs=0
more-Itertools__39Mm2jr reward=-         exc=no  apt_errs=0
flask-restful__6KAohgZ  reward=1.000000  exc=no  apt_errs=0
flask-restful__VDLzPdk  reward=1.000000  exc=no  apt_errs=0
flask-restful__3gjirmY  reward=0.000000  exc=no  apt_errs=0   (nop control)
```

`deepdiff` is the bullseye case — the one the v2 fix targets. Its trial.log
contains **zero `apt-get update|install` invocations**, and its
`agent/opencode.txt` is at 745KB updated within the minute, i.e. well past
setup and actively running.

The reason is the *other* half of the original repair: pinning Node v22 into
the image makes Harbor's `ensure_system_dependencies` probe succeed, and that
function **returns early without shelling out to apt**. The archive rewrite
was only ever defense-in-depth for something else in the image invoking apt;
nothing does.

**Conclusion:** the security-suite deletion is worth keeping in the generator
for correctness, but it is not blocking anything and no re-verification run is
needed. Zero exceptions across all 7 fixup trials.

### 429 urgency: correctly downgraded

All 4 quota failures hit within ~16 minutes of startup, when 8 agents began
simultaneously; none in the hours since, and endpoint probes return 200. A
startup burst, not an ongoing bleed. The concurrency 2->1 change already
applied to the configs stays (it costs nothing and removes the herd at the
next relaunch), but it needed no restart and none was performed.

## 12. Reconciliation: does the apt fix still matter? (both measurements were right)

The parent session measured `apt_errs=0` and **zero apt-get invocations** across
its 7 fixup trials; I measured **22 of 36 trials invoking apt-get**, including
all 8 APT_404 failures. Both are correct -- they were measuring *different
datasets*.

The fixup tasks (`datasets/nl2repo-fixup`) carry an extra Dockerfile layer that
installs a **pinned Node v22.23.2 from a checksummed official tarball**. Harbor's
opencode setup probes `command -v node && command -v npm` first and only falls
through to `apt-get install ... nodejs npm` when that fails. With Node
preinstalled the probe returns early, so **apt is never reached**:

```
MAIN  deepdiff  -> Running command: apt-get update && apt-get install ...   (404, exit 100)
FIXUP deepdiff  -> Running command: set -euo pipefail; if ldd --version ... (apt=0, 895 KB agent output)
```

**Conclusion for the 8 APT_404 trials:** they are recoverable *only* by
regenerating against a task definition that avoids the apt path. The Node-pin
approach is strictly better than my sources.list rewrite:

- it removes the dependency on any distro feed rather than repairing one;
- it is deterministic (pinned version + sha256), so it cannot drift;
- it sidesteps the fact that the images ship **Node v12.22.12 / npm 7.5.2**
  (what my apt fix installs) -- ancient, and a plausible source of further
  opencode failures.

My `archive.debian.org` fix is still worth keeping for correctness (any task
that *does* reach apt on an EOL base will now work, and deleting the
`debian-security` line rather than rewriting it is required -- that suite does
not exist on the archive). But it is the fallback, not the primary fix.

## 13. Final accounting: NL2Repo-Bench main jobs (20 trials, both finished ~4h)

```
10  REWARDED        (5 instances x 2 models, all scored)
 8  APT_404         (4 instances x 2 models: deepdiff, flask-restful,
                     graphneuralnetwork, pyperclip -- agent never ran)
 2  RuntimeError    (more-Itertools x 2: "Docker compose command failed" --
                     the image-name casing bug, fixed after these launched)
--
20  total -- fully accounted for, nothing unexplained
```

Rewards (identical instances across both models, which is itself a good
consistency signal):

```
paillier        1.000000 / 1.000000      sklearn    0.985714 / 0.985714
stamina         0.983871 / 0.983871      mootdx     0.666667 / 0.657143
mechanicalsoup  1.000000 / 0.000000
```

Only `mechanicalsoup` diverges between models, and the 0.000000 side is the
**429 quota** trial (`qvyiCUS`) -- an infrastructure loss, not a luna/terra
capability difference. Reward parity everywhere else suggests the harness is
measuring stably.


### Correction: apt DOES still matter — I measured the wrong dataset

An earlier entry above ("Apt fix v2 is unnecessary") generalized from the
**fixup** trials to all trials. That was wrong. Measured across both:

```
main nl2repo trials invoking apt-get:  18
fixup trials invoking apt-get:          0
```

Both observations were correct; they were of **different task definitions**.
The fixup Dockerfile preinstalls a checksummed Node v22.23.2 tarball, and
Harbor's `ensure_system_dependencies` probes `command -v node && npm` before
falling through to `apt-get install nodejs npm` — so the fixup path never
reaches apt, while the un-regenerated main path still does and still 404s.

**Consequence:** the 8 `ARTIFACT_APT_404` trials are **not** already fine.
They are recoverable only by regenerating those tasks against a definition
that avoids the apt path.

**Which fix is primary.** The Node pin, not the archive rewrite:

- it removes the distro-feed dependency rather than repairing it, and is
  deterministic (pinned version + sha256);
- the apt path, even when repaired, installs **Node v12.22.12 / npm 7.5.2**
  from bullseye — ancient, and a plausible source of downstream opencode
  failures. A "working" apt fix would have quietly shipped a Node three major
  versions behind what opencode expects.

Keep the `archive.debian.org` rewrite (with `debian-security` **deleted**, not
rewritten — that suite does not exist on the archive) only as a fallback for
any task that still reaches apt.

### NL2Repo final accounting — 20 trials, nothing unexplained

```
10  REWARDED
 8  ARTIFACT_APT_404      deepdiff, flask-restful, graphneuralnetwork, pyperclip (x2 models)
 2  ARTIFACT_RuntimeError more-Itertools x2 -- "Docker compose command failed" (casing bug)
```

No new failure classes. The 429s are not in this set; they hit SWE-bench-Pro
and `mechanicalsoup`, and `mechanicalsoup` still scored.

Cross-model parity on the rewarded trials is near-exact:

```
paillier        1.000000 / 1.000000     sklearn   0.985714 / 0.985714
stamina         0.983871 / 0.983871     mootdx    0.666667 / 0.657143
mechanicalsoup  1.000000 / 0.000000
```

Only `mechanicalsoup` diverges, and the zero side is the 429 quota trial
(`qvyiCUS`) — an infrastructure loss, not a luna/terra capability gap. That
parity is a useful stability signal for the harness itself.

## 14. Later-emerging artifacts (found after the NL2Repo jobs finished)

### apt 404 also hits SWE-bench-Pro (not just NL2Repo)
`ARTIFACT_APT_404` rose 8 -> 10 as `gravitational/teleport` trials landed on
both models. Their images are **bullseye** too, with 4 x `404 Not Found`. So the
EOL-Debian problem is not NL2Repo-specific -- any task whose base is an archived
Debian release and whose setup reaches apt will fail the same way. The Node-pin
fix (parent session's approach) covers these as well, since it stops setup ever
reaching apt.

Note these are *gravitational* trials, i.e. Go -- already unmeasurable here for
the qemu reason. They would need the Node pin **and** real x86 to yield data.

### `ApiRateLimitError` is mislabeled -- it is an OOM, not a rate limit
One trial (`instance_internetarchive__openli__bStsLW`, terra) is recorded by
Harbor as `ApiRateLimitError`. That label is wrong, and taking it at face value
would send a future investigator hunting a quota problem that does not exist:

```
exception : ApiRateLimitError, "Command failed (exit 137): ... opencode run ..."
429 markers in opencode.txt : 0        (a real quota failure leaves "cooling down")
opencode.txt                : 333 KB   (the agent had been working normally)
task memory_mb              : 4096
host free memory            : 54 GB    (so the HOST was not short of memory)
```

**Exit 137 = 128 + 9 = SIGKILL.** With no 429 markers, plenty of host memory,
and a hard 4096 MB per-task cap, this is the container's cgroup OOM-killing
opencode -- `internetarchive/openlibrary` is a heavy Python repo and opencode
holds a large context. Compare the genuine quota failures, which carry
`"All credentials ... are cooling down"` and `statusCode: 429` (see Artifact D).

**Implication:** distinguish these two. A real 429 is a provider capacity issue
that resolves on its own; an OOM is fixed by raising `memory_mb` for that task.
`triage_rewards.py` currently trusts Harbor's exception type here and will
report it as `ARTIFACT_ApiRateLimitError`; treat that verdict as
"agent killed -- check for exit 137 and 0 x 429 markers before assuming quota".

## 15. Why TypeScript still has zero trustworthy data (4 trials, 4 different artifacts)

All 17 TS/JS instances are measurable in principle -- the language is not
blocked the way Go is -- but every TS trial completed so far has been lost to a
*different* artifact:

```
protonmail cENF6s2  ARTIFACT_AGENT_NEVER_STARTED       0-byte opencode.txt, 100 min
protonmail t9zVbpW  ARTIFACT_TIMEOUT_BUDGET_TOO_SMALL  384 KB, killed mid-step
tutao      rCo7Tw   ARTIFACT_GRADER_NAME_MISMATCH      tests passed, name unmatched
tutao      DD4qHm   ARTIFACT_MODEL_QUOTA_429           provider cooldown
```

This is bad luck rather than a systematic TS problem, but it means **no TS
conclusion can be drawn yet**, and the per-language table correctly shows
nothing rather than a fabricated 0.000.

### AgentTimeoutError conflates two different failures
The two protonmail trials shared one exception type but are not the same event,
and they need opposite responses:

- `cENF6s2`: **0 bytes** of agent output over the full 100 minutes -- the agent
  never issued a model call (the startup hang in section 10). Retrying is the
  right response; more time would not have helped.
- `t9zVbpW`: **384 KB** and still completing steps at the cutoff (last record is
  a `step-finish` with 62 120 tokens and cache reads). Genuine work, truncated.
  Here the budget really is too small: `timeout_sec = 3000` x2 = 6000 s, and
  `protonmail/webclients` is a large monorepo whose file operations are slow
  under emulation.

`triage_rewards.py` now splits these into `ARTIFACT_AGENT_NEVER_STARTED` and
`ARTIFACT_TIMEOUT_BUDGET_TOO_SMALL` by output size, so the fix is obvious from
the verdict. If TS trials keep hitting the cap, raise
`--agent-timeout-multiplier` from 2 to 3-4 for the SWE-bench-Pro jobs.

### Go containment confirmed
All 10 `ARTIFACT_NO_TESTS_RAN` are Go, and no non-Go trial has ever landed in
that class. The qemu defect is exactly as scoped -- it has not leaked into
Python, TypeScript or JavaScript.

## 16. Zero tests is not automatically an artifact (correction from the parent session)

`triage_rewards.py` classified any trial with `output.json == {"tests": []}` as
`ARTIFACT_NO_TESTS_RAN`. That rule is too broad. The parent session found, in
the reference corpus, that some zero-test trials are **pytest collection
errors** -- the agent's own patch broke an import, so nothing could be
collected. That is a *genuine model failure* and must stay in the scored set;
excluding it discards real signal (narrowing the exclusion moved
`premature_stop` to the strongest result in their mapping).

Two further corrections to what I had written earlier:

- The zero-test artifact is **not Go-exclusive in general**. The reference
  bundles contain 31 TypeScript and 6 Python zero-test trials. It is Go-only
  *in these DGX runs*, which is a fact about this hardware, not about the
  benchmark.
- So "Go containment breaking" would not have invalidated anything. My monitor
  alert on that was also a false positive: it matched the indented summary
  counter line (`  ARTIFACT_NO_TESTS_RAN    16`) and read "16" as a language.
  Detail rows start at column 1; the fixed check anchors with `^`.

The classifier now checks the verifier stdout for `ERROR collecting`,
`ImportError`, `ModuleNotFoundError` or `errors during collection` before
quarantining a zero-test trial, and scores it `GENUINE_FAIL` when present.

**Verified against the current DGX runs: zero reclassifications** -- all 16
zero-test trials there are Go runtime crashes with no collection error, so the
counts are unchanged. The guard matters for future runs and for any re-analysis
of the reference corpus.

## 17. Go-free switch: AUTHORISED and armed (v2)

The user approved switching SWE-bench-Pro to the 43-task Go-free dataset; the
cost projection in section 15 is what informed it (2.1 trials/h/job, ~34 Go
trials remaining ~= 8h of the projected 24h producing nothing measurable).

Armed by the parent session as `switch_nogo_v2.sh`, tmux `nogo-v2`, log
`logs/nogo-v2.log`. **This is expected automation -- do not escalate it as
unattributed.** Two fixes over the version that was killed:

1. **No deadline.** v1 switched after 2h regardless of drain, which would have
   killed live trials. v2 waits indefinitely for a real drain.
2. **Orphans excluded from the live count.** A trial is live only if it has
   neither a reward nor an `exception.txt`. Harbor reaps a timed-out trial but
   leaves its container running at ~100% CPU forever; counting those would
   block the drain permanently.

On firing it kills both `dsm-swebenchpro-*` sessions, repoints the configs at
`datasets/swebenchpro-nogo`, and relaunches at concurrency 1. Harbor skips
completed trials in the same `jobs_dir`, so the existing rewards survive.

Monitoring adjusted accordingly: watching relaunch completion (a failed
relaunch would silently end the run) and orphaned containers (each blocks the
drain); Go-containment watch dropped as moot post-switch.


### Concurrency restored to 2 before the switch relaunch (2026-09-07 07:51)

The 2->1 drop was applied when 429 quota failures looked like an ongoing
bleed. They were not. All four cluster at **00:03-00:19** — a thundering herd
from 8 agents starting simultaneously — with **none in the 7.5h since**, and
endpoint probes returning 200 throughout.

Leaving concurrency at 1 through the relaunch would have roughly halved
throughput against ~16h of remaining non-Go work, buying nothing: the pressure
it guards against was a startup transient, and the relaunch itself is the only
moment that recreates a simultaneous start. Restored to 2 in the
`swebenchpro-*` configs before `switch_nogo_v2` fires, so the relaunch picks
it up.

If 429s do reappear after the relaunch, staggering the two job starts is the
better lever than halving concurrency permanently — it removes the herd
without paying for it in wall-clock for the rest of the run.
