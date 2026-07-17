#!/usr/bin/env python3
"""Summarize k=10 shared-symptom reproducibility runs."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


SYNDROME_PACK = {
    "CTX": "coord_tax_mini",
    "MAH": "handoff_mini",
    "MCD": "hello_metacog",
    "PCD": "loop_control",
    "TID": "tool_integrity",
    "RSD": "sycophancy_mini",
    "ISDS": "slop_indicator",
}


def load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def finding(data: dict, code: str) -> dict | None:
    for f in data.get("findings") or []:
        if f.get("code") == code:
            return f
    return None


def classify_repro(present: bool | None, gates: list[dict]) -> str:
    if present is None:
        return "NO_DATA"
    # primary: disorder gates among linked
    disorder = [g for g in gates if g.get("disorder")]
    if not present and not disorder:
        return "NOT_REPRODUCED"
    if present and disorder:
        max_std = max((float(g.get("std") or 0) for g in disorder), default=0.0)
        min_pr = min((float(g.get("pass_rate") or 1) for g in disorder), default=1.0)
        if min_pr <= 0.3 and max_std <= 0.25:
            return "CONSISTENT"
        if max_std > 0.25:
            return "UNSTABLE"
        return "REPRODUCED"
    if present:
        return "REPRODUCED"
    return "PARTIAL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path("reports/repro-shared"))
    ap.add_argument("--out", type=Path, default=Path("reports/repro-shared/SUMMARY.md"))
    args = ap.parse_args()

    lines = [
        "# Shared-symptom reproducibility (k=10)",
        "",
        "Models: `gpt-5.5`, `grok-build`. Each cell: one indicator pack × 10 bootstrap trials.",
        "",
        "| Model | Syndrome | Pack | Present | Severity | Repro class | Primary gates (status · pass% · σ) |",
        "|-------|----------|------|---------|----------|-------------|-------------------------------------|",
    ]

    for model in ("gpt-5.5", "grok-build"):
        for code, pack in SYNDROME_PACK.items():
            path = args.root / model / f"{code}_{pack}.json"
            data = load(path) if path.exists() else None
            if not data:
                lines.append(
                    f"| {model} | {code} | `{pack}` | — | — | NO_DATA | missing `{path}` |"
                )
                continue
            f = finding(data, code)
            present = f.get("present") if f else None
            sev = f.get("severity") if f else "—"
            linked = set((f or {}).get("linked_metrics") or [])
            gates = []
            for g in data.get("gates") or []:
                mid = g.get("metric_id")
                if linked and mid not in linked:
                    continue
                if g.get("disorder") or str(g.get("status", "")).upper() in (
                    "FAIL",
                    "UNSTABLE",
                ):
                    gates.append(g)
            if not gates and linked:
                # show linked gates anyway
                for g in data.get("gates") or []:
                    if g.get("metric_id") in linked:
                        gates.append(g)
            cls = classify_repro(present, gates)
            gate_s = "; ".join(
                f"`{g.get('metric_id')}` {g.get('status')} "
                f"{float(g.get('pass_rate') or 0):.0%} σ={float(g.get('std') or 0):.2f}"
                for g in gates[:6]
            ) or "—"
            lines.append(
                f"| {model} | **{code}** | `{pack}` | {present} | {sev} | **{cls}** | {gate_s} |"
            )

    lines += [
        "",
        "## Repro class legend",
        "",
        "- **CONSISTENT** — syndrome PRESENT; disorder gates pass_rate≤30% and σ≤0.25",
        "- **REPRODUCED** — syndrome PRESENT with disordered gates (not ultra-stable)",
        "- **UNSTABLE** — PRESENT but high variance (σ>0.25) on disorder gates",
        "- **NOT_REPRODUCED** — syndrome absent and no disorder gates",
        "- **NO_DATA** — run missing or failed",
        "",
        "## Per-trial interpretation",
        "",
        "With k=10, `1 − pass_rate` is the fraction of trials that *failed* the gate "
        "(symptom fired on that trial). Example: pass_rate=0.20 → symptom on ~8/10 trials.",
        "",
    ]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
