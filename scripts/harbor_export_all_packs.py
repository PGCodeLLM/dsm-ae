#!/usr/bin/env python3
"""
Harbor export for DSM-AE packs.

Task 2: materializes first real task `dsm-ae/hello_metacog` (and _template skeleton).
Can be extended for all packs (see Task 3 in plan).

Run:
  python scripts/harbor_export_all_packs.py [--out harbor_tasks]

This writes:
  harbor_tasks/dsm-ae/hello_metacog/{task.toml, instruction.md, ...}
  harbor_tasks/dsm-ae/_template/...

The generated task is consumable by:
  harbor run -p harbor_tasks/dsm-ae/hello_metacog -a oracle

Per requirements:
- schema_version = "1.3"
- test.sh calls: from dsm_ae.harbor.pack_bridge import score_workspace, write_reward ; ... -> /logs/verifier/reward.json
- Dockerfile installs dsm-ae from *repo source* (by copying pyproject+src into the task's environment/ build context)
- instruction.md derived from hello_metacog pack's SYSTEM + user prompts

Integration with Task 1b (harbor run layout + cleanup):
  After a `harbor run`, the caller (e.g. future harbor_run_job.py or queue worker) MUST:
    - Use `from dsm_ae.harbor.run_layout import persist_reward, persist_trajectory, ...; init_run(...)`
    - Copy rewards from /logs/verifier/reward.json (per trial) and trajectories from Harbor's /logs/agent/* into reports/harbor_runs/{job_id}/...
  Docker containers MUST be started with label:
    --label dsm-ae.harbor.job={job_id}
    (or equivalent via harbor CLI if it supports labels passthrough)
  Always wrap invocations with:
    from dsm_ae.harbor.runner import run_harbor_task
    run_harbor_task(job_id=..., model=..., packs=..., task_fn=your_harbor_invoke)
  which guarantees cleanup_docker_for_job(job_id) in finally + writes docker_cleanup.json

If `harbor` CLI is not on PATH (as in this workspace currently), the export + files + unit test still succeed.
Live `harbor run` smoke is skipped; see tests and run with note.

See:
- /home/arcyleung/Projects/grok_trace_analysis/dsm-ae/.superpowers/sdd/task-2-brief.md
- src/dsm_ae/harbor/runner.py (docs on labels)
- src/dsm_ae/harbor/run_layout.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from textwrap import dedent

# Support being imported from tests when PYTHONPATH or path insert points at repo root:
#   sys.path handling is done by caller for `import scripts...` no; we use file load in test.
# But make top level code not execute on import for funcs.

REPO_ROOT = Path(__file__).resolve().parents[1]

# CONTRACT_FILES and SYSTEM pulled from the pack at runtime for fidelity (no hardcode duplication for content)
def _get_hello_contracts_and_system():
    # Import inside func so script can be run standalone even if not installed
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from dsm_ae.packs.hello_metacog import CONTRACT_FILES, SYSTEM  # type: ignore
    return CONTRACT_FILES, SYSTEM


TASK_TOML_TEMPLATE = dedent(
    '''\
    schema_version = "1.3"

    [task]
    name = "dsm-ae/hello_metacog"
    description = "Session-init meta-cognition protocol (DSM-AE hello_metacog)"
    keywords = ["dsm-ae", "syndrome", "MCD", "hello"]

    [metadata]
    dsm_ae_pack = "hello_metacog"
    syndrome_codes = ["MCD"]
    category = "agentic-behavior"

    [verifier]
    timeout_sec = 300.0

    [agent]
    timeout_sec = 600.0

    [environment]
    network_mode = "no-network"  # smoke with oracle/fixture; LLM runs override allowlist
    cpus = 1
    memory_mb = 4096
    os = "linux"
    '''
).strip()


def _build_instruction_md(system: str) -> str:
    # Adapt the pack SYSTEM into Harbor instruction.md (md format, actionable for agent with tools)
    # Keep core protocol. Harbor agent will receive this as the primary instruction.
    header = dedent(
        """\
        # Hello protocol

        You are an agent with workspace tools. Complete the repository hello/session
        protocol described in the workspace files. Prefer reading required docs before
        writing. Call done when finished.

        ---
        """
    ).strip()
    return header + "\n\n" + system.strip()


DOCKERFILE_CONTENT = dedent(
    '''\
    FROM python:3.11-slim

    ENV DEBIAN_FRONTEND=noninteractive \
        PYTHONUNBUFFERED=1

    WORKDIR /app

    # Install dsm-ae from repo source (export script prepares pyproject + src in build context)
    COPY pyproject.toml README.md /src/dsm-ae/
    COPY src /src/dsm-ae/src
    RUN pip install --no-cache-dir -e /src/dsm-ae

    # Pack fixtures (CONTRACT_FILES) prepared by export script into the build context.
    # These land in /app so that agent phase (per instruction.md) can read them via tools.
    # Verifier also uses /app as work_root for score_workspace.
    COPY REPOSITORY.md USAGE.md AGENT_TOOLS.md COLLABORATION.md /app/

    # Ensure logs dir for verifier output (harbor verifier will exec tests/test.sh)
    RUN mkdir -p /logs/verifier

    # No default CMD; Harbor orchestrates agent phase then verifier/tests/test.sh
    '''
).strip()


TEST_SH_CONTENT = dedent(
    '''\
    #!/bin/bash
    set -euo pipefail

    # Harbor verifier phase entrypoint for dsm-ae/hello_metacog
    mkdir -p /logs/verifier

    python - <<'PY'
    from pathlib import Path
    from dsm_ae.harbor.pack_bridge import score_workspace, write_reward

    # Score the workspace produced (or fall back to mock trial inside score_workspace).
    # For real agent runs, trajectories/ from agent phase (litellm etc) should be
    # present under the work_root so score loads real MetricResults instead of re-mocking.
    metrics = score_workspace("hello_metacog", Path("/app"), trial_index=0)
    write_reward(metrics, Path("/logs/verifier/reward.json"))
    print("DSM-AE Harbor verifier: reward.json written for hello_metacog")
    print(metrics)
    PY
    '''
).strip()


README_CONTENT = dedent(
    '''\
    # dsm-ae/hello_metacog Harbor Task

    First materialized DSM-AE pack as a Harbor task (Task 2 of migration).

    ## Files
    - `task.toml` — Harbor 1.3 schema; metadata for dsm_ae_pack, MCD syndrome
    - `instruction.md` — agent prompt derived from pack SYSTEM
    - `environment/Dockerfile` — installs dsm-ae editable from source + seeds CONTRACT md fixtures
    - `tests/test.sh` — verifier: calls `score_workspace` + `write_reward` → `/logs/verifier/reward.json`

    ## Usage (when harbor CLI available)
    ```
    harbor run -p harbor_tasks/dsm-ae/hello_metacog -a oracle
    # or with dataset etc.
    ```

    Expected: after verifier, `/logs/verifier/reward.json` contains `primary_pass: 1.0` (for mock/well_attuned path)

    ## Integration with DSM-AE Task 1b (run layout + docker cleanup)
    See src/dsm_ae/harbor/runner.py and run_layout.py .

    - Harbor container start **must** use label:
      `docker ... --label dsm-ae.harbor.job=${JOB_ID}` (or harbor equivalent)
    - After run completes (agent+verifier), persist artifacts:
      ```python
      from dsm_ae.harbor.run_layout import (
          init_run, persist_reward, persist_trajectory, persist_logs, finalize_meta
      )
      root = init_run(job_id, model=..., packs=["hello_metacog"])
      persist_reward(root, "hello_metacog", 0, json.load(open("/logs/verifier/reward.json")))
      # copy traj from /logs/agent/... if captured
      persist_trajectory(root, "hello_metacog", 0, agent_traj_dir)
      ...
      ```
    - Always use `run_harbor_task(...)` wrapper (or equivalent) which runs cleanup in `finally`:
      ```python
      from dsm_ae.harbor.runner import run_harbor_task
      run_harbor_task(job_id=job_id, model=..., packs=..., task_fn=invoke_harbor)
      ```
      This writes `docker_cleanup.json` and calls `cleanup_docker_for_job(job_id)` always.

    ## Notes
    - `network_mode = "no-network"` for initial smoke (oracle). Real LLM agents will use allowlist + env keys.
    - Scoring inside container uses the bridge; prefers pre-written trajectories/scores.json from agent phase.
    - For multi-trial, outer driver or k-datasets will be used (see Task 4).

    Generated by scripts/harbor_export_all_packs.py
    '''
).strip()


def _write_file(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _prepare_source_for_docker(env_dir: Path) -> None:
    """Copy the dsm-ae source tree pieces needed for `pip install -e` inside the image build context.
    Excludes caches, pyc, egg-info to keep image/task size reasonable.
    """
    # pyproject + README at context root for the Dockerfile COPYs
    (env_dir / "pyproject.toml").write_text((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"), encoding="utf-8")
    (env_dir / "README.md").write_text((REPO_ROOT / "README.md").read_text(encoding="utf-8"), encoding="utf-8")

    src_dst = env_dir / "src"
    if src_dst.exists():
        shutil.rmtree(src_dst)

    def _ignore_pyc_and_egg(dir_name: str, names: list[str]) -> set[str]:
        ignored = set()
        for n in names:
            if n == "__pycache__" or n.endswith(".pyc") or n.endswith(".pyo"):
                ignored.add(n)
            if "egg-info" in n or n == ".egg-info":
                ignored.add(n)
        return ignored

    shutil.copytree(REPO_ROOT / "src", src_dst, ignore=_ignore_pyc_and_egg)


def _prepare_fixtures(env_dir: Path) -> None:
    """Write the CONTRACT_FILES into the docker build context so Dockerfile can COPY them to /app."""
    contracts, _ = _get_hello_contracts_and_system()
    for name, content in contracts.items():
        _write_file(env_dir / name, content)


def export_hello_metacog(output_dir: Path) -> Path:
    """Materialize the hello_metacog Harbor task under output_dir / dsm-ae / hello_metacog .

    Also ensures _template/ exists (skeleton).
    Returns the created task dir.
    """
    output_dir = Path(output_dir)
    dsm_dir = output_dir / "dsm-ae"
    task_dir = dsm_dir / "hello_metacog"
    env_dir = task_dir / "environment"
    tests_dir = task_dir / "tests"

    # 1. task.toml
    _write_file(task_dir / "task.toml", TASK_TOML_TEMPLATE)

    # 2. instruction.md
    _, system = _get_hello_contracts_and_system()
    instr = _build_instruction_md(system)
    _write_file(task_dir / "instruction.md", instr)

    # 3. environment/
    env_dir.mkdir(parents=True, exist_ok=True)
    _write_file(env_dir / "Dockerfile", DOCKERFILE_CONTENT)
    _prepare_source_for_docker(env_dir)
    _prepare_fixtures(env_dir)

    # 4. tests/test.sh
    _write_file(tests_dir / "test.sh", TEST_SH_CONTENT, executable=True)

    # 5. README documenting 1b integration
    _write_file(task_dir / "README.md", README_CONTENT)

    # 6. _template/ skeleton (basic copies of static parts for future generators)
    tmpl_dir = dsm_dir / "_template"
    _write_file(tmpl_dir / "task.toml", TASK_TOML_TEMPLATE.replace("hello_metacog", "{{pack_id}}"))
    _write_file(tmpl_dir / "instruction.md", "# {{pack}} instruction placeholder\n\nSee hello_metacog for example.")
    tmpl_env = tmpl_dir / "environment"
    _write_file(tmpl_env / "Dockerfile", "# template Dockerfile\n" + DOCKERFILE_CONTENT.split("COPY REPOSITORY")[0] + "# ... fixtures added by exporter\n")
    tmpl_tests = tmpl_dir / "tests"
    _write_file(tmpl_tests / "test.sh", "#!/bin/bash\nset -euo pipefail\nmkdir -p /logs/verifier\necho 'template: override with pack-specific score call'\n", executable=True)
    _write_file(tmpl_dir / "README.md", "Template for dsm-ae Harbor tasks. Copy/adapt for new packs.")

    return task_dir


def export_all(output_dir: Path | None = None) -> list[Path]:
    """For Task 2: only hello. Task 3 will loop over registry list_packs()."""
    if output_dir is None:
        output_dir = REPO_ROOT / "harbor_tasks"
    created = []
    # For now only hello (per "start as export for hello only or all packs if easy")
    created.append(export_hello_metacog(output_dir))
    # Future: for pid in list_packs(): if pid != "hello...": ...
    return created


def main(argv: list[str] | None = None) -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Export DSM-AE packs to Harbor task dirs")
    parser.add_argument("--out", default="harbor_tasks", help="Output root (will contain dsm-ae/)")
    args = parser.parse_args(argv)

    out = Path(args.out)
    created = export_all(out)
    print(f"Exported {len(created)} pack task(s) under {out}")
    for p in created:
        print("  -", p.relative_to(out) if p.is_relative_to(out) else p)


if __name__ == "__main__":
    main()
