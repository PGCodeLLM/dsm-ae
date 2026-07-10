#!/usr/bin/env python3
"""Summarize DSM-AE reports into a comparison matrix."""
from pathlib import Path
import re

reports = sorted(Path("reports").glob("gpt-*.md")) + sorted(Path("reports").glob("grok-build.md"))
# exclude BLOCKED
reports = [p for p in reports if "BLOCKED" not in p.name]

def parse(path: Path):
    text = path.read_text(encoding="utf-8")
    model = re.search(r"\*\*Model:\*\* `([^`]+)`", text)
    model = model.group(1) if model else path.stem
    findings = {}
    for code in ["MCD", "OASD", "ISDS", "SC-35"]:
        m = re.search(rf"### `{re.escape(code)}`[^\n]*\[(PRESENT|absent)\]", text)
        findings[code] = m.group(1) if m else "?"
    gates = {}
    for line in text.splitlines():
        # | dim | `metric` | 0.83 | ... | **PASS** | yes |
        m = re.match(
            r"\| [^|]+ \| `([^`]+)` \| ([0-9.]+) \| ([0-9.]+) \| ([0-9.]+) \| \*\*([A-Z]+)\*\* \| (yes|no) \|",
            line,
        )
        if m:
            gates[m.group(1)] = {
                "pass": float(m.group(2)),
                "mean": float(m.group(3)),
                "std": float(m.group(4)),
                "status": m.group(5),
                "disorder": m.group(6) == "yes",
            }
    return model, findings, gates

rows = []
for p in reports:
    try:
        rows.append(parse(p))
    except Exception as e:
        print(f"skip {p}: {e}")

out = Path("reports/COMPARISON.md")
lines = ["# DSM-AE Multi-Model Comparison", "", f"Reports: {len(rows)}", ""]
lines.append("## Syndromes")
lines.append("")
lines.append("| Model | MCD | OASD | ISDS | SC-35 | Report |")
lines.append("|-------|-----|------|------|-------|--------|")
for model, findings, gates in rows:
    lines.append(
        f"| `{model}` | {findings.get('MCD')} | {findings.get('OASD')} | "
        f"{findings.get('ISDS')} | {findings.get('SC-35')} | `reports/{model}.md` |"
    )
lines.append("")
lines.append("## Key gates (pass rate / status)")
lines.append("")
key_metrics = [
    "protocol_success",
    "files_read_complete",
    "overeager_rate",
    "scope_safe",
    "critical_trap_avoided",
    "erosion_indicator",
    "verbosity_indicator",
    "task_success_cleanup",
]
header = "| Model | " + " | ".join(f"`{m}`" for m in key_metrics) + " |"
sep = "|-------|" + "|".join(["------"] * len(key_metrics)) + "|"
lines.append(header)
lines.append(sep)
for model, findings, gates in rows:
    cells = []
    for m in key_metrics:
        g = gates.get(m)
        if not g:
            cells.append("—")
        else:
            cells.append(f"{g['pass']:.0%} {g['status']}")
    lines.append(f"| `{model}` | " + " | ".join(cells) + " |")
lines.append("")
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {out}")
print(out.read_text())
