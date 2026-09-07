"""Load Harbor / EvalHub run bundles into a DSM-AE-scoreable shape.

Input layout (one *run* = one benchmark job):

    <run>/<instance_dir>/
        agent/trajectory.json   # ATIF-v1.x: {schema_version, agent, steps[], final_metrics}
        verifier/reward.txt     # external oracle, "1" / "0"
        result.json             # task_name, trial_name, source, config

The trajectory carries `steps[]`, each optionally with `tool_calls[]` of the
shape `{tool_call_id, function_name, arguments}` and an `observation.results[]`
holding the tool output. We flatten that to the flat `{name, arguments, result,
error}` dicts the DSM-AE intent labeller and atom vocabulary already consume,
so every existing off-policy instrument works unchanged.

Nothing here interprets *task success*: reward comes from the verifier, which
is deliberately not a DSM-AE gate. That independence is what makes the
behaviour->task mapping non-circular.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

# Repo -> primary language. SWE-bench-Pro spans several ecosystems; language is
# the main confound to stratify on when asking "is this an agentic deficit or
# just weak C++/Go training?".
REPO_LANG: dict[str, str] = {
    "ansible": "python",
    "qutebrowser": "python",
    "internetarchive": "python",
    "gravitational": "go",
    "flipt-io": "go",
    "navidrome": "go",
    "future-architect": "go",
    "element-hq": "typescript",
    "protonmail": "typescript",
    "nodebb": "javascript",
    "tutao": "typescript",
}


@dataclass
class HarborTrial:
    """One agentic task attempt with an external outcome oracle."""

    run: str
    source: str  # swebenchpro | nl2repobench | ...
    trial_name: str
    task_name: str
    repo: str
    language: str
    reward: float | None
    n_tests_run: int | None = None  # None = verifier output absent/unparsed
    exception_type: str | None = None  # harness-level failure from result.json
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    reasoning: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)
    n_steps: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    task_prompt: str = ""

    @property
    def scoreable(self) -> bool:
        """Whether this trial's reward is a measurement of the *model*.

        Two ways it is not:

        1. **The verifier ran zero tests.** An empty `tests` list in
           `verifier/output.json` means the trial was scored 0 without any test
           executing — a broken exec path, not a model failure. Counting those
           as failures inflates the failure rate of whichever ecosystem is
           affected (here Go: 20.8% of Go trials vs 1.1% of Python), which
           would manufacture exactly the language-deficit conclusion this study
           exists to rule out.
        2. **The harness itself failed.** `result.json.exception_info` records
           trial-level failures — `NetworkConnectionError`, `AgentTimeoutError`,
           `NonZeroAgentExitCodeError`, `UnknownApiError`,
           `AgentAuthenticationError`, `VerifierTimeoutError`. These are
           infrastructure, not behaviour, and they are invisible in `trial.log`,
           which is why an earlier pass reported "zero errors" while 119
           reference trials carried one.

        Note both are *structural* disqualifications: the record shows the
        measurement could not have happened. A reward that merely disagrees
        with a partial success signal is NOT excluded — see the defense Q/A
        (Q18) for the case that was adjudicated and rejected.

        Trials with no `output.json` at all stay scoreable; absence of the file
        is not evidence that nothing ran.
        """
        return self.n_tests_run != 0 and self.exception_type is None

    @property
    def success(self) -> bool | None:
        if self.reward is None or not self.scoreable:
            return None
        return self.reward >= 1.0

    def as_trace(self) -> dict[str, Any]:
        """Shape accepted by the intent labeller / atom fingerprinter."""
        return {
            "trial_id": self.trial_name,
            "pack": f"harbor:{self.source}",
            "tool_calls": self.tool_calls,
            "final_text": self.messages[-1] if self.messages else "",
            "scaffold_card": {"model": self.run, "pack": f"harbor:{self.source}"},
        }


def _norm_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}
        return parsed if isinstance(parsed, dict) else {"raw": raw}
    return {}


def _result_index(step: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Map tool_call_id -> its observation entry."""
    obs = step.get("observation") or {}
    results = obs.get("results") if isinstance(obs, dict) else None
    idx: dict[str, dict[str, Any]] = {}
    for r in results or []:
        if isinstance(r, dict):
            cid = str(r.get("source_call_id") or r.get("tool_call_id") or "")
            if cid:
                idx[cid] = r
    return idx


def _flatten_result(entry: dict[str, Any] | None) -> tuple[str | None, str | None]:
    """Return (result_text, error_text) for one observation entry."""
    if not entry:
        return None, None
    err = entry.get("error")
    for key in ("output", "content", "result", "text", "stdout"):
        val = entry.get(key)
        if val:
            text = val if isinstance(val, str) else json.dumps(val)
            return text, (str(err) if err else None)
    if err:
        return None, str(err)
    return None, None


def _parse_trajectory(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


def _repo_of(trial_name: str, task_name: str) -> str:
    """SWE-bench-Pro trial names look like `instance_<org>__<repo>-<sha>__<id>`."""
    stem = trial_name.removeprefix("instance_")
    head = stem.split("__", 1)[0]
    if head and head != "task":
        return head
    m = re.search(r"/([^/]+?)(?:-[0-9a-f]{6,})?$", task_name or "")
    return m.group(1) if m else "unknown"


def load_trial(inst_dir: Path, *, run: str) -> HarborTrial | None:
    traj_path = inst_dir / "agent" / "trajectory.json"
    res_path = inst_dir / "result.json"
    if not traj_path.exists() or not res_path.exists():
        return None

    try:
        traj = _parse_trajectory(traj_path)
        result = json.loads(res_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None

    reward: float | None = None
    rw = inst_dir / "verifier" / "reward.txt"
    if rw.exists():
        try:
            reward = float(rw.read_text().strip())
        except ValueError:
            reward = None

    # How many tests the verifier actually executed. Zero means the reward is
    # not a measurement of the model — see HarborTrial.scoreable.
    # Harness-level failure. Recorded in result.json, NOT in trial.log — a
    # trial can fail here while trial.log looks perfectly healthy.
    exception_type: str | None = None
    einfo = result.get("exception_info")
    if einfo:
        if isinstance(einfo, dict):
            exception_type = str(
                einfo.get("exception_type") or einfo.get("type") or "unknown"
            )
        else:
            exception_type = str(einfo)[:80]

    n_tests_run: int | None = None
    vo = inst_dir / "verifier" / "output.json"
    if vo.exists():
        try:
            vd = json.loads(vo.read_text())
        except (json.JSONDecodeError, OSError):
            vd = None
        if isinstance(vd, dict) and isinstance(vd.get("tests"), list):
            n_tests_run = len(vd["tests"])

    trial_name = str(result.get("trial_name") or inst_dir.name)
    task_name = str(result.get("task_name") or "")
    source = str(result.get("source") or "").strip()
    if not source:
        source = "nl2repobench" if "nl2repo" in run else "swebenchpro"
    repo = _repo_of(trial_name, task_name)

    calls: list[dict[str, Any]] = []
    reasoning: list[str] = []
    messages: list[str] = []
    task_prompt = ""

    steps = traj.get("steps") or []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if step.get("source") == "user" and not task_prompt:
            task_prompt = str(step.get("message") or "")
        msg = step.get("message")
        if msg:
            messages.append(str(msg))
        rc = step.get("reasoning_content")
        if rc:
            # ATIF interleaves streaming chunks with stray newlines.
            reasoning.append(re.sub(r"\n{2,}", " ", str(rc)).strip())

        ridx = _result_index(step)
        for tc in step.get("tool_calls") or []:
            if not isinstance(tc, dict):
                continue
            cid = str(tc.get("tool_call_id") or "")
            res_text, err_text = _flatten_result(ridx.get(cid))
            calls.append(
                {
                    "id": cid,
                    "name": str(tc.get("function_name") or tc.get("name") or ""),
                    "arguments": _norm_args(tc.get("arguments")),
                    "result": res_text,
                    "error": err_text,
                }
            )

    fm = traj.get("final_metrics") or {}
    return HarborTrial(
        run=run,
        source=source,
        trial_name=trial_name,
        task_name=task_name,
        repo=repo,
        language=REPO_LANG.get(repo, "python" if source.startswith("nl2repo") else "unknown"),
        reward=reward,
        n_tests_run=n_tests_run,
        exception_type=exception_type,
        tool_calls=calls,
        reasoning=reasoning,
        messages=messages,
        n_steps=int(fm.get("total_steps") or len(steps)),
        prompt_tokens=int(fm.get("total_prompt_tokens") or 0),
        completion_tokens=int(fm.get("total_completion_tokens") or 0),
        task_prompt=task_prompt,
    )


def load_run(run_dir: Path) -> list[HarborTrial]:
    """Load every instance under one extracted run bundle."""
    run_dir = Path(run_dir)
    trials: list[HarborTrial] = []
    seen: set[Path] = set()
    for res in run_dir.rglob("result.json"):
        inst = res.parent
        if inst in seen or not (inst / "agent" / "trajectory.json").exists():
            continue
        seen.add(inst)
        t = load_trial(inst, run=run_dir.name)
        if t is not None:
            trials.append(t)
    return trials


def iter_runs(root: Path) -> Iterator[tuple[str, list[HarborTrial]]]:
    for run_dir in sorted(Path(root).iterdir()):
        if run_dir.is_dir():
            yield run_dir.name, load_run(run_dir)
