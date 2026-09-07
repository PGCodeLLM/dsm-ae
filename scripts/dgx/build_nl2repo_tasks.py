#!/usr/bin/env python3
"""Generate Harbor tasks for NL2Repo-Bench.

There is no public Harbor adapter for NL2Repo-Bench, so this reconstructs one
from the two upstream sources that ARE public:

  1. Environment images: ghcr.io/multimodal-art-projection/nl2repobench/<name>:1.0
     Each ships /workspace with only pyproject.toml + tests/ -- the agent has to
     write the implementation. (Mirrored as .tar on the HF dataset
     YTL-AI-Labs-Data-XP-1/NL2Repo, but GHCR pulls directly.)
  2. Task spec: github.com/multimodal-art-projection/NL2RepoBench
     test_files/<name>/{start.md, test_commands.json, test_case_count.txt}

`start.md` is the requirements document the agent must implement. It is NOT
baked into the public image, so we stage it into /workspace ourselves -- the
reference trajectories' first user turn says "According to the start.md in the
workspace, implement the entire project as per the requirements specified in
the document", confirming that is where the original harness put it.

Reward is FRACTIONAL (passed pytest cases / total), matching the reference
bundles, which carry values like 0.436573 rather than 0/1.

Usage:
  python build_nl2repo_tasks.py --out ~/dsm-dgx/datasets/nl2repobench \
      --instances deepdiff flask-restful ...
"""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/multimodal-art-projection/NL2RepoBench/main/test_files"
IMAGE = "ghcr.io/multimodal-art-projection/nl2repobench/{name}:1.0"

INSTRUCTION = """\
According to the start.md in the workspace, implement the entire project as per \
the requirements specified in the document, ensuring that the final product can \
be directly run in the current directory. The running requirements should comply \
with the <API Usage Guide> section of the document. Please complete this task \
step by step.

The requirements document is at /workspace/start.md. The existing tests under
/workspace/tests define the expected behaviour; do not modify them.
"""

DOCKERFILE = """\
# NL2Repo-Bench ships pre-built environments on GHCR.
FROM {image}

# Reset entrypoint so the harness can run its own command.
ENTRYPOINT []

WORKDIR /workspace

# The requirements document the agent must implement against. It is not baked
# into the public image, so it is staged in here from the upstream repo.
COPY start.md /workspace/start.md
"""

# Fractional reward: passed / total pytest cases, matching the reference bundles.
TEST_SH = r"""#!/bin/bash
# NL2Repo-Bench verifier: fractional reward = passed test cases / total.
set -uo pipefail

REWARD_FILE="${REWARD_FILE:-/logs/verifier/reward.txt}"
mkdir -p "$(dirname "$REWARD_FILE")"
echo 0 > "$REWARD_FILE"

cd /workspace

REPORT=/tmp/nl2repo_report.json

{TEST_COMMANDS}

python3 - <<'PYEOF'
import json, os, re, sys

report = "/tmp/nl2repo_report.json"
reward_file = os.environ.get("REWARD_FILE", "/logs/verifier/reward.txt")
total_expected = int(open("/tmp/nl2repo_total.txt").read().strip() or "0")

passed = total = 0
try:
    with open(report) as fh:
        data = json.load(fh)
    tests = data.get("tests", [])
    total = len(tests)
    passed = sum(1 for t in tests if t.get("outcome") == "passed")
except Exception as exc:  # noqa: BLE001 - verifier must never hard-fail
    print(f"could not parse json report ({exc}); falling back to stdout parse")
    try:
        text = open("/tmp/nl2repo_stdout.txt").read()
        m = re.search(r"(\d+) passed", text)
        passed = int(m.group(1)) if m else 0
        f = re.search(r"(\d+) failed", text)
        e = re.search(r"(\d+) error", text)
        total = passed + (int(f.group(1)) if f else 0) + (int(e.group(1)) if e else 0)
    except Exception:
        pass

# Prefer the benchmark's declared case count as the denominator so that
# collection errors (which hide tests) are penalised rather than ignored.
denom = max(total, total_expected)
reward = (passed / denom) if denom else 0.0
print(f"passed={passed} total={total} declared={total_expected} reward={reward:.6f}")
with open(reward_file, "w") as fh:
    fh.write(f"{reward:.6f}\n")
PYEOF
"""


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "curl"})
    with urllib.request.urlopen(req, timeout=60) as fh:
        return fh.read().decode()


def build_task(name: str, out_dir: Path) -> None:
    start_md = fetch(f"{RAW}/{name}/start.md")
    commands = json.loads(fetch(f"{RAW}/{name}/test_commands.json"))
    try:
        count = fetch(f"{RAW}/{name}/test_case_count.txt").strip()
    except Exception:
        count = "0"

    task = out_dir / name
    (task / "tests").mkdir(parents=True, exist_ok=True)
    (task / "environment").mkdir(parents=True, exist_ok=True)
    (task / "solution").mkdir(parents=True, exist_ok=True)

    (task / "instruction.md").write_text(INSTRUCTION)
    (task / "environment" / "start.md").write_text(start_md)
    # Docker repository names must be lowercase. The upstream repo's
    # test_files/ dirs preserve the package's original casing (e.g.
    # "more-Itertools"), but the published GHCR image is all-lowercase.
    (task / "environment" / "Dockerfile").write_text(
        DOCKERFILE.format(image=IMAGE.format(name=name.lower()))
    )

    # Run the benchmark's own commands, but tee stdout and add a json report to
    # the pytest invocation so the reward can be computed per test case.
    lines = []
    for cmd in commands:
        if cmd.strip().startswith("pytest"):
            cmd = (
                f"{cmd} --json-report --json-report-file=$REPORT "
                "2>&1 | tee /tmp/nl2repo_stdout.txt"
            )
            lines.append("pip install pytest-json-report >/dev/null 2>&1 || true")
        lines.append(cmd)
    body = "\n".join(lines)

    test_sh = TEST_SH.replace("{TEST_COMMANDS}", body)
    (task / "tests" / "test.sh").write_text(test_sh)
    (task / "tests" / "total.txt").write_text(count + "\n")
    # test.sh reads the declared count from /tmp; stage it at the top.
    (task / "tests" / "test.sh").write_text(
        test_sh.replace(
            "cd /workspace",
            f'cd /workspace\necho "{count}" > /tmp/nl2repo_total.txt',
            1,
        )
    )

    (task / "task.toml").write_text(
        f"""schema_version = "1.0"

[task]
name = "map/nl2repobench__{name}"
authors = [{{ name = "MAP (multimodal-art-projection)" }}]
keywords = ["code-generation", "nl2repobench"]

[metadata]
difficulty = "hard"
category = "code-generation"

[verifier]
network_mode = "public"
timeout_sec = 3000

[agent]
network_mode = "public"
timeout_sec = 7200

[environment]
build_timeout_sec = 1800.0
cpus = 2
memory_mb = 8192
storage_mb = 20480
gpus = 0
"""
    )
    print(f"OK   {name}  (declared cases: {count})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--instances", nargs="+", required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    ok = fail = 0
    for name in args.instances:
        try:
            build_task(name, args.out)
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAIL {name}: {exc!r}")
            fail += 1
    print(f"Done. Success: {ok}  Failures: {fail}")


if __name__ == "__main__":
    main()
