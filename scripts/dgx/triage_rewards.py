#!/usr/bin/env python3
"""Separate GENUINE task failures from INFRASTRUCTURE artifacts in a run tree.

A reward of 0 means two very different things:

  * the agent tried and the required test really failed   -> genuine signal
  * no test ever ran (emulation/exec failure, timeout)    -> meaningless zero

Reporting the second kind as model performance would fabricate a
language-specific deficit, which is exactly the confound this study exists to
separate from genuine agentic deficits. This script makes the distinction
explicit and auditable.

Run ON THE DGX (or over a pulled run tree):
    python3 triage_rewards.py ~/dsm-dgx/runs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Repo -> primary language, mirroring src/dsm_ae/harbor/adapter.py.
REPO_LANG = {
    "ansible": "python", "qutebrowser": "python", "internetarchive": "python",
    "gravitational": "go", "flipt-io": "go", "navidrome": "go",
    "future-architect": "go", "element-hq": "typescript",
    "protonmail": "typescript", "nodebb": "javascript", "tutao": "typescript",
}


def language_of(trial: str) -> str:
    # SWE-bench-Pro trials are "instance_<owner>__...__<suffix>"; NL2Repo-Bench
    # trials are "<package>__<suffix>" and are all Python.
    if not trial.startswith("instance_"):
        return "python"  # NL2Repo-Bench
    name = trial.replace("instance_", "", 1).split("__")[0].lower()
    return REPO_LANG.get(name, "unknown")


def classify(trial_dir: Path) -> dict:
    reward_f = trial_dir / "verifier" / "reward.txt"
    out_f = trial_dir / "verifier" / "output.json"
    if not reward_f.exists():
        return {"verdict": "INCOMPLETE", "reward": None, "n_tests": None}

    try:
        reward = float(reward_f.read_text().strip())
    except ValueError:
        return {"verdict": "BAD_REWARD_FILE", "reward": None, "n_tests": None}

    n_tests = None
    if out_f.exists():
        try:
            n_tests = len(json.loads(out_f.read_text()).get("tests", []))
        except Exception:
            n_tests = None

    if reward > 0:
        verdict = "GENUINE_PASS"
    elif n_tests == 0:
        # Verifier produced no test results at all -> nothing was measured.
        verdict = "ARTIFACT_NO_TESTS_RAN"
    elif n_tests is None:
        # NL2Repo-Bench computes a fractional reward directly and writes no
        # output.json; a 0 there means tests ran and none passed. SWE-bench-Pro
        # always writes output.json, so a missing one is genuinely suspicious.
        verdict = ("GENUINE_FAIL" if not trial_dir.name.startswith("instance_")
                   else "UNKNOWN_NO_OUTPUT_JSON")
    else:
        # Tests ran and were named; a 0 here is a real failure. (Name-matching
        # graders can still under-report -- see README section 9, artifact B.)
        verdict = "GENUINE_FAIL"
    return {"verdict": verdict, "reward": reward, "n_tests": n_tests}


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "runs").expanduser()
    rows = []
    for job in sorted(p for p in root.iterdir() if p.is_dir()):
        for trial in sorted(p for p in job.iterdir() if p.is_dir()):
            info = classify(trial)
            info.update(job=job.name, trial=trial.name,
                        language=language_of(trial.name))
            rows.append(info)

    if not rows:
        print(f"no trials under {root}")
        return

    print(f"{'verdict':<24} {'lang':<11} {'reward':>8} {'tests':>6}  trial")
    print("-" * 88)
    for r in sorted(rows, key=lambda r: (r["verdict"], r["trial"])):
        rw = "-" if r["reward"] is None else f"{r['reward']:.4f}"
        nt = "-" if r["n_tests"] is None else str(r["n_tests"])
        print(f"{r['verdict']:<24} {r['language']:<11} {rw:>8} {nt:>6}  {r['trial'][:40]}")

    print("\n== counts by verdict ==")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<24} {v}")

    print("\n== TRUSTWORTHY scoring rate, by language ==")
    print("   (artifacts excluded -- they measured nothing)")
    by_lang: dict[str, list[float]] = {}
    for r in rows:
        if r["verdict"] in ("GENUINE_PASS", "GENUINE_FAIL"):
            by_lang.setdefault(r["language"], []).append(r["reward"])
    for lang in sorted(by_lang):
        v = by_lang[lang]
        print(f"  {lang:<12} n={len(v):3d}  mean={sum(v)/len(v):.3f}")

    quarantined = sum(1 for r in rows if r["verdict"].startswith(("ARTIFACT", "UNKNOWN")))
    if quarantined:
        print(f"\n!! {quarantined} trial(s) QUARANTINED -- do not report these as "
              f"model performance (see scripts/dgx/README-runs.md section 9).")


if __name__ == "__main__":
    main()
