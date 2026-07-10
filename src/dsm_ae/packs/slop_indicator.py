"""Slop indicator — 2-checkpoint mini protocol (NOT full SlopCodeBench).

C1: implement simple search CLI
C2: extend for multi-language filter

Measures indicator of structural erosion / verbosity growth, not full benchmark.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from dsm_ae.adapters.raw_loop import RawToolLoopAdapter, fresh_workspace
from dsm_ae.models import MetricEvidence, MetricResult, TrialTrace
from dsm_ae.packs.base import IndicatorPack

SEED = '''"""search CLI seed — agent extends this."""
import argparse
from pathlib import Path

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--pattern", required=True)
    args = ap.parse_args()
    # TODO: implement search
    print("not implemented")

if __name__ == "__main__":
    main()
'''

SYSTEM = """You are a coding agent.
PROTOCOL TAG: SLOP_CHECKPOINT
Edit main.py in the workspace to satisfy the checkpoint specification.
Prefer small modular functions over one giant function.
Call done(message=...) when finished.
"""


class SlopIndicatorPack(IndicatorPack):
    id = "slop_indicator"
    name = "Slop / Structural Quality Indicator (2 checkpoints)"
    dimensions = [
        "c1_implements",
        "c2_extends",
        "erosion_indicator",
        "verbosity_indicator",
        "quality_stable",
    ]
    patterns = ["CQ-01", "CQ-02", "CQ-10", "CQ-26"]

    def run_trial(
        self, adapter: RawToolLoopAdapter, work_root: Path, trial_index: int
    ) -> list[TrialTrace]:
        ws = fresh_workspace(work_root / f"slop_t{trial_index}")
        (ws / "main.py").write_text(SEED, encoding="utf-8")
        traces = []

        specs = [
            (
                1,
                "SLOP_CHECKPOINT 1: Implement a Python CLI in main.py that searches "
                "files under root for --pattern (regex) and prints matching paths. "
                "Keep helpers small.",
            ),
            (
                2,
                "SLOP_CHECKPOINT 2: Extend the program to support optional --langs "
                "filter (e.g. .py .js). Do not rewrite everything into one function.",
            ),
        ]
        for ckpt, user in specs:
            tr = adapter.run(
                pack=self.id,
                scenario_id=f"slop_indicator/c{ckpt}",
                system_prompt=SYSTEM,
                user_prompt=user,
                workspace=ws,
                trial_index=trial_index,
                variant=f"c{ckpt}",
            )
            code = (ws / "main.py").read_text(encoding="utf-8") if (ws / "main.py").exists() else ""
            tr.meta["code"] = code
            tr.meta["checkpoint"] = ckpt
            tr.meta["code_metrics"] = analyze_code(code)
            traces.append(tr)
        return traces

    def score(self, trace: TrialTrace) -> list[MetricResult]:
        code = trace.meta.get("code") or ""
        cm = trace.meta.get("code_metrics") or analyze_code(code)
        ckpt = int(trace.meta.get("checkpoint") or 1)

        implements = "re" in code or "regex" in code.lower() or "search" in code
        if ckpt == 1:
            c1 = "argparse" in code and ("Path" in code or "os.walk" in code or "rglob" in code)
            c2 = True  # N/A
            c1_pass = bool(c1 and implements)
            c2_pass = True
        else:
            c1_pass = True
            c2_pass = ("langs" in code.lower() or "suffix" in code or ".js" in code) and implements

        # erosion indicator: share of complexity in functions with cc>10, or single huge function
        erosion = float(cm.get("erosion", 0.0))
        verbosity = float(cm.get("verbosity", 0.0))
        # pass thresholds for *indicator* (lenient vs full bench)
        erosion_ok = erosion <= 0.5
        verbosity_ok = verbosity <= 0.45
        # quality_stable scored only meaningfully on c2; for c1 always pass placeholder
        if ckpt == 1:
            stable_ok = erosion_ok and verbosity_ok
            stable_val = 1.0 if stable_ok else 0.0
        else:
            # if we have prior in meta chain — pack scorer sees single trace;
            # stable uses absolute thresholds as indicator
            stable_ok = erosion_ok and verbosity_ok
            stable_val = 1.0 if stable_ok else 0.0

        return [
            MetricResult(
                metric_id="c1_implements",
                value=1.0 if (c1_pass if ckpt == 1 else True) else 0.0,
                passed=c1_pass if ckpt == 1 else True,
                explanation=f"C1 implement gate (ckpt={ckpt}): {c1_pass if ckpt==1 else 'n/a on c2'}.",
                evidence=[MetricEvidence(kind="derived", ref="code", detail=code[:200])],
                patterns=["CQ-10"],
                raw={"ckpt": ckpt, "metrics": cm},
            ),
            MetricResult(
                metric_id="c2_extends",
                value=1.0 if (c2_pass if ckpt == 2 else True) else 0.0,
                passed=c2_pass if ckpt == 2 else True,
                explanation=f"C2 extend gate (ckpt={ckpt}): {c2_pass if ckpt==2 else 'n/a on c1'}.",
                evidence=[MetricEvidence(kind="derived", ref="code", detail=code[:200])],
                patterns=["CQ-10"],
            ),
            MetricResult(
                metric_id="erosion_indicator",
                value=erosion,
                passed=erosion_ok,
                explanation=(
                    f"Structural erosion indicator={erosion:.3f} "
                    f"(mass in CC>10 funcs / total; pass ≤0.5). "
                    f"max_cc={cm.get('max_cc')}, n_funcs={cm.get('n_funcs')}, loc={cm.get('loc')}."
                ),
                evidence=[
                    MetricEvidence(
                        kind="derived",
                        ref="erosion",
                        detail=str(cm),
                    )
                ],
                patterns=["CQ-01"],
                raw=cm,
            ),
            MetricResult(
                metric_id="verbosity_indicator",
                value=verbosity,
                passed=verbosity_ok,
                explanation=(
                    f"Verbosity indicator={verbosity:.3f} "
                    f"(duplicate/branchy line ratio proxy; pass ≤0.45). "
                    f"dup_lines={cm.get('dup_lines')}, loc={cm.get('loc')}."
                ),
                evidence=[
                    MetricEvidence(kind="derived", ref="verbosity", detail=str(verbosity))
                ],
                patterns=["CQ-02"],
                raw=cm,
            ),
            MetricResult(
                metric_id="quality_stable",
                value=stable_val,
                passed=stable_ok,
                explanation=(
                    "Quality stable if erosion_ok ∧ verbosity_ok at this checkpoint."
                ),
                evidence=[],
                patterns=["CQ-01", "CQ-02", "CQ-26"],
                raw={"erosion_ok": erosion_ok, "verbosity_ok": verbosity_ok},
            ),
        ]


def analyze_code(code: str) -> dict:
    """Lightweight erosion/verbosity proxies (no radon dependency)."""
    loc = max(len([ln for ln in code.splitlines() if ln.strip()]), 1)
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {
            "loc": loc,
            "n_funcs": 0,
            "max_cc": 0,
            "erosion": 1.0,
            "verbosity": 1.0,
            "dup_lines": 0,
            "parse_error": True,
        }

    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    masses = []
    max_cc = 0
    for fn in funcs:
        cc = cyclomatic(fn)
        # approximate sloc of function
        if hasattr(fn, "end_lineno") and fn.end_lineno and fn.lineno:
            sloc = max(fn.end_lineno - fn.lineno + 1, 1)
        else:
            sloc = 10
        mass = cc * (sloc ** 0.5)
        masses.append((cc, mass, fn.name))
        max_cc = max(max_cc, cc)

    total_mass = sum(m for _, m, _ in masses) or 1.0
    hot_mass = sum(m for cc, m, _ in masses if cc > 10)
    # also treat single-function programs with cc>8 as eroded
    if len(funcs) <= 1 and max_cc > 8:
        erosion = max(hot_mass / total_mass, 0.7)
    else:
        erosion = hot_mass / total_mass

    # verbosity: repeated stripped lines / loc
    lines = [re.sub(r"\s+", " ", ln.strip()) for ln in code.splitlines() if ln.strip()]
    from collections import Counter

    counts = Counter(lines)
    dup_lines = sum(c for ln, c in counts.items() if c > 1 and len(ln) > 8)
    verbosity = min(dup_lines / loc, 1.0)
    # boost verbosity if one huge function
    if len(funcs) <= 1 and loc > 40:
        verbosity = max(verbosity, 0.5)

    return {
        "loc": loc,
        "n_funcs": len(funcs),
        "max_cc": max_cc,
        "erosion": float(erosion),
        "verbosity": float(verbosity),
        "dup_lines": dup_lines,
        "funcs": [name for _, _, name in masses],
    }


def cyclomatic(fn: ast.AST) -> int:
    """Simple CC: 1 + branches."""
    score = 1
    for n in ast.walk(fn):
        if isinstance(n, (ast.If, ast.For, ast.While, ast.ExceptHandler, ast.With, ast.Assert)):
            score += 1
        elif isinstance(n, ast.BoolOp):
            score += max(len(n.values) - 1, 0)
        elif isinstance(n, ast.comprehension):
            score += 1
    return score
