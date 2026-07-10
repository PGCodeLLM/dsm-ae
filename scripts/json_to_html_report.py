#!/usr/bin/env python3
"""Build a cross-model HTML matrix from DSM-AE diagnosis JSON reports.

Usage:
  python3 scripts/json_to_html_report.py
  python3 scripts/json_to_html_report.py --input reports --out reports/index.html
  python3 scripts/json_to_html_report.py reports/**/*.json -o comparison.html

If models did not run the same packs/metrics, cells show NOT RUN.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def discover_jsons(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".json":
            found.append(p)
        elif p.is_dir():
            found.extend(sorted(p.rglob("*.json")))
    # de-dupe, stable
    out: list[Path] = []
    seen: set[Path] = set()
    for p in found:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        out.append(p)
    return out


def load_report(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    # must look like DiagnosisReport
    if "gates" not in data and "findings" not in data:
        return None
    if "scaffold_card" not in data and "packs" not in data:
        return None
    data["_source_path"] = str(path)
    return data


def model_id(report: dict[str, Any]) -> str:
    card = report.get("scaffold_card") or {}
    return str(card.get("model") or report.get("model") or "unknown")


def merge_reports(reports: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Merge multiple JSON runs per model.

    Later files override earlier metric/finding cells for the same key,
    but packs are unioned so NOT RUN stays accurate for never-run packs.
    """
    by_model: dict[str, dict[str, Any]] = {}
    for rep in reports:
        mid = model_id(rep)
        if mid not in by_model:
            by_model[mid] = {
                "model": mid,
                "packs": set(),
                "gates": {},  # metric_id -> gate dict
                "findings": {},  # code -> finding dict
                "sources": [],
                "k_trials": [],
                "run_ids": [],
            }
        acc = by_model[mid]
        packs = rep.get("packs") or []
        if isinstance(packs, list):
            acc["packs"].update(packs)
        acc["sources"].append(rep.get("_source_path", ""))
        if rep.get("run_id"):
            acc["run_ids"].append(rep["run_id"])
        if rep.get("k_trials") is not None:
            acc["k_trials"].append(rep["k_trials"])
        for g in rep.get("gates") or []:
            mid_g = g.get("metric_id") or g.get("dimension")
            if not mid_g:
                continue
            acc["gates"][mid_g] = g
        for f in rep.get("findings") or []:
            code = f.get("code")
            if not code:
                continue
            acc["findings"][code] = f
    return by_model


def collect_universe_fixed(by_model: dict[str, dict[str, Any]]):
    models = sorted(by_model.keys())
    metrics: set[str] = set()
    findings: set[str] = set()
    packs: set[str] = set()
    for acc in by_model.values():
        metrics.update(acc["gates"].keys())
        findings.update(acc["findings"].keys())
        packs.update(acc["packs"])
    return models, sorted(metrics), sorted(findings), sorted(packs)


def status_class(status: str | None, not_run: bool = False) -> str:
    if not_run:
        return "not-run"
    s = (status or "").upper()
    if s == "PASS":
        return "pass"
    if s == "FAIL":
        return "fail"
    if s == "UNSTABLE":
        return "unstable"
    if s == "SKIP":
        return "skip"
    return "unknown"


def fmt_gate_cell(gate: dict[str, Any] | None) -> tuple[str, str]:
    if gate is None:
        return "NOT RUN", "not-run"
    status = str(gate.get("status") or "?")
    pr = gate.get("pass_rate")
    std = gate.get("std")
    disorder = gate.get("disorder")
    try:
        pr_s = f"{float(pr):.0%}"
    except Exception:
        pr_s = "?"
    try:
        std_s = f"{float(std):.2f}"
    except Exception:
        std_s = "?"
    dis = " · disorder" if disorder else ""
    text = f"{status} · {pr_s} · σ={std_s}{dis}"
    return text, status_class(status)


def fmt_finding_cell(finding: dict[str, Any] | None) -> tuple[str, str]:
    if finding is None:
        return "NOT RUN", "not-run"
    present = finding.get("present")
    sev = finding.get("severity") or "none"
    if present:
        return f"PRESENT · {sev}", "present"
    return f"absent · {sev}", "absent"


def build_html(
    by_model: dict[str, dict[str, Any]],
    title: str = "DSM-AE Multi-Model Report",
) -> str:
    models, metrics, finding_codes, packs = collect_universe_fixed(by_model)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def th_models() -> str:
        return "".join(f"<th class='model'>{html.escape(m)}</th>" for m in models)

    # packs matrix
    pack_rows = []
    for pack in packs:
        cells = []
        for m in models:
            ran = pack in by_model[m]["packs"]
            if ran:
                cells.append("<td class='pass'>RUN</td>")
            else:
                cells.append("<td class='not-run'>NOT RUN</td>")
        pack_rows.append(
            f"<tr><th class='row'>{html.escape(pack)}</th>{''.join(cells)}</tr>"
        )

    # gates matrix
    gate_rows = []
    for metric in metrics:
        cells = []
        for m in models:
            text, cls = fmt_gate_cell(by_model[m]["gates"].get(metric))
            title_attr = ""
            g = by_model[m]["gates"].get(metric)
            if g and g.get("explanation"):
                title_attr = f" title=\"{html.escape(str(g['explanation'])[:400])}\""
            cells.append(f"<td class='{cls}'{title_attr}>{html.escape(text)}</td>")
        gate_rows.append(
            f"<tr><th class='row'><code>{html.escape(metric)}</code></th>{''.join(cells)}</tr>"
        )

    # findings matrix
    finding_rows = []
    for code in finding_codes:
        # resolve display name from any model that has it
        name = code
        for m in models:
            f = by_model[m]["findings"].get(code)
            if f and f.get("name"):
                name = f"{code} — {f['name']}"
                break
        cells = []
        for m in models:
            text, cls = fmt_finding_cell(by_model[m]["findings"].get(code))
            f = by_model[m]["findings"].get(code)
            title_attr = ""
            if f and f.get("rationale"):
                title_attr = f" title=\"{html.escape(str(f['rationale'])[:400])}\""
            cells.append(f"<td class='{cls}'{title_attr}>{html.escape(text)}</td>")
        finding_rows.append(
            f"<tr><th class='row'>{html.escape(name)}</th>{''.join(cells)}</tr>"
        )

    # sources list
    source_blocks = []
    for m in models:
        acc = by_model[m]
        srcs = [s for s in acc["sources"] if s]
        packs_s = ", ".join(sorted(acc["packs"])) or "(none)"
        k_s = ", ".join(str(k) for k in acc["k_trials"]) or "?"
        source_blocks.append(
            f"<li><strong>{html.escape(m)}</strong> — packs: "
            f"<code>{html.escape(packs_s)}</code>; k: {html.escape(k_s)}; "
            f"sources: {html.escape('; '.join(srcs) if srcs else '—')}</li>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(title)}</title>
<style>
  :root {{
    --bg: #0f1419;
    --panel: #1a2332;
    --text: #e7ecf3;
    --muted: #9aa7b8;
    --border: #2a3648;
    --pass: #1f6f4a;
    --fail: #8b2e2e;
    --unstable: #8a6d1d;
    --not-run: #3a4556;
    --present: #8b2e2e;
    --absent: #1f6f4a;
    --skip: #3a4556;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px;
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: var(--bg); color: var(--text); line-height: 1.45;
  }}
  h1, h2 {{ margin: 0 0 12px; font-weight: 650; }}
  h2 {{ margin-top: 32px; font-size: 1.15rem; color: #c9d4e3; }}
  p, li {{ color: var(--muted); }}
  .meta {{ margin-bottom: 20px; font-size: 0.92rem; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 10px; margin: 12px 0 20px; }}
  .legend span {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 4px 10px; border-radius: 999px; font-size: 0.8rem;
    border: 1px solid var(--border); background: var(--panel);
  }}
  .swatch {{ width: 10px; height: 10px; border-radius: 2px; display: inline-block; }}
  .swatch.pass, td.pass {{ background: var(--pass); }}
  .swatch.fail, td.fail {{ background: var(--fail); }}
  .swatch.unstable, td.unstable {{ background: var(--unstable); }}
  .swatch.not-run, td.not-run {{ background: var(--not-run); color: #c5cdd8; font-style: italic; }}
  .swatch.present, td.present {{ background: var(--present); }}
  .swatch.absent, td.absent {{ background: var(--absent); }}
  .panel {{
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 12px; padding: 12px; overflow: auto; margin-bottom: 8px;
  }}
  table {{ border-collapse: separate; border-spacing: 0; min-width: 100%; font-size: 0.86rem; }}
  th, td {{
    border-bottom: 1px solid var(--border);
    border-right: 1px solid var(--border);
    padding: 8px 10px; text-align: center; vertical-align: middle;
  }}
  th.model {{
    position: sticky; top: 0; background: #121a26; z-index: 2;
    min-width: 120px;
  }}
  th.corner {{
    position: sticky; left: 0; top: 0; background: #121a26; z-index: 3;
    text-align: left;
  }}
  th.row {{
    position: sticky; left: 0; background: #152032; text-align: left;
    z-index: 1; max-width: 280px; font-weight: 600;
  }}
  td {{ color: #fff; font-variant-numeric: tabular-nums; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.84em; }}
  footer {{ margin-top: 28px; color: var(--muted); font-size: 0.82rem; }}
</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="meta">
    Generated {html.escape(generated)} ·
    {len(models)} model(s) ·
    {len(packs)} pack(s) ·
    {len(metrics)} metric(s) ·
    {len(finding_codes)} syndrome(s)
  </div>
  <div class="legend">
    <span><i class="swatch pass"></i> PASS / RUN / absent</span>
    <span><i class="swatch fail"></i> FAIL / PRESENT</span>
    <span><i class="swatch unstable"></i> UNSTABLE</span>
    <span><i class="swatch not-run"></i> NOT RUN</span>
  </div>

  <h2>Pack coverage</h2>
  <p>Whether each model executed a given indicator pack in any loaded JSON.</p>
  <div class="panel">
    <table>
      <thead><tr><th class="corner">Pack</th>{th_models()}</tr></thead>
      <tbody>
        {''.join(pack_rows) if pack_rows else '<tr><td colspan="99">No packs found</td></tr>'}
      </tbody>
    </table>
  </div>

  <h2>Syndrome matrix</h2>
  <p>Composite diagnoses. Hover cells for rationale when available.</p>
  <div class="panel">
    <table>
      <thead><tr><th class="corner">Syndrome</th>{th_models()}</tr></thead>
      <tbody>
        {''.join(finding_rows) if finding_rows else '<tr><td colspan="99">No findings found</td></tr>'}
      </tbody>
    </table>
  </div>

  <h2>Outcome-gate matrix</h2>
  <p>Status · pass-rate · σ. Hover for per-gate explanation. Missing metrics show <em>NOT RUN</em>.</p>
  <div class="panel">
    <table>
      <thead><tr><th class="corner">Metric</th>{th_models()}</tr></thead>
      <tbody>
        {''.join(gate_rows) if gate_rows else '<tr><td colspan="99">No gates found</td></tr>'}
      </tbody>
    </table>
  </div>

  <h2>Sources</h2>
  <ul>
    {''.join(source_blocks)}
  </ul>

  <footer>
    DSM-AE HTML report · cells with incomplete cross-model pack coverage are marked NOT RUN ·
    generated from diagnosis JSON only
  </footer>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "inputs",
        nargs="*",
        type=Path,
        default=[Path("reports")],
        help="JSON files or directories (default: reports/)",
    )
    ap.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("reports/dsm-ae-matrix.html"),
        help="Output HTML path",
    )
    ap.add_argument("--title", default="DSM-AE Multi-Model Report")
    ap.add_argument(
        "--include-mock",
        action="store_true",
        help="Include mock/* models (excluded by default)",
    )
    args = ap.parse_args(argv)

    paths = discover_jsons(list(args.inputs))
    reports: list[dict[str, Any]] = []
    for p in paths:
        rep = load_report(p)
        if not rep:
            continue
        mid = model_id(rep)
        if (not args.include_mock) and mid.startswith("mock/"):
            continue
        reports.append(rep)

    if not reports:
        print("No diagnosis JSON reports found.", file=sys.stderr)
        return 1

    by_model = merge_reports(reports)
    html_doc = build_html(by_model, title=args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html_doc, encoding="utf-8")
    print(f"Wrote {args.out} ({len(by_model)} models, {len(reports)} json files)")
    models, metrics, findings, packs = collect_universe_fixed(by_model)
    print(f"  models: {', '.join(models)}")
    print(f"  packs: {len(packs)}, metrics: {len(metrics)}, syndromes: {len(findings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
