#!/usr/bin/env python3
"""Build a cross-model HTML matrix from DSM-AE diagnosis JSON reports.

Includes clinical-style expandable diagnostic decision trees (FPG-like)
with per-model pathway tracing and trajectory evidence.

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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from dsm_ae.metric_citations import citations_for_metric, references_used
    from dsm_ae.decision_trees import (
        SYNDROME_TREES,
        PathwayResult,
        TreeNode,
        evaluate_tree,
        gates_from_report_acc,
        tree_to_mermaid,
    )
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from dsm_ae.metric_citations import citations_for_metric, references_used
    from dsm_ae.decision_trees import (
        SYNDROME_TREES,
        PathwayResult,
        TreeNode,
        evaluate_tree,
        gates_from_report_acc,
        tree_to_mermaid,
    )


def discover_jsons(paths: list[Path]) -> list[Path]:
    found: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".json":
            found.append(p)
        elif p.is_dir():
            found.extend(sorted(p.rglob("*.json")))
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

    Later files override earlier metric/finding/bootstrap cells for the same key;
    packs are unioned so NOT RUN stays accurate for never-run packs.
    """
    by_model: dict[str, dict[str, Any]] = {}
    for rep in reports:
        mid = model_id(rep)
        if mid not in by_model:
            by_model[mid] = {
                "model": mid,
                "packs": set(),
                "gates": {},
                "findings": {},
                "bootstraps": {},  # metric_id -> bootstrap dict
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
        for b in rep.get("bootstraps") or []:
            mid_b = b.get("metric_id")
            if not mid_b:
                continue
            acc["bootstraps"][mid_b] = b
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
    # include catalogue syndrome codes even if no findings yet
    findings.update(SYNDROME_TREES.keys())
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


# ---------------------------------------------------------------------------
# Decision tree HTML — Mermaid directed graphs (FPG-style)
# ---------------------------------------------------------------------------


def _esc(s: Any) -> str:
    return html.escape(str(s) if s is not None else "")


def render_mermaid_block(mermaid_src: str, caption: str = "") -> str:
    """Deferred Mermaid block — not rendered until the parent <details> opens.

    Source is stored in a non-executable script tag so mermaid.startOnLoad
    never walks hundreds of graphs on first paint.
    """
    cap = f'<div class="flow-title">{_esc(caption)}</div>' if caption else ""
    # Guard against accidental </script> in graph text; keep Mermaid syntax intact.
    safe = mermaid_src.replace("</script", "<\\/script")
    return (
        f'<div class="mermaid-wrap" data-lazy-mermaid="1">'
        f"{cap}"
        f'<div class="mermaid-host" hidden></div>'
        f'<script type="text/plain" class="mermaid-src">{safe}</script>'
        f'<noscript><pre class="mermaid-fallback">{_esc(mermaid_src)}</pre></noscript>'
        f"</div>"
    )


def render_reference_flowchart(tree) -> str:
    """Reference algorithm as Mermaid directed decision graph (lazy)."""
    mm = tree_to_mermaid(tree, title=f"{tree.code} reference algorithm")
    bits = [
        f'<p class="flow-desc">{_esc(tree.description)}</p>',
        f'<p class="flow-metrics"><strong>Sub-criteria (metrics):</strong> '
        + ", ".join(f"<code>{_esc(m)}</code>" for m in tree.linked_metrics)
        + ". Rounded boxes fan into diamonds = polythetic inputs; "
        "diamonds = yes/no criteria; stadiums/rects = diagnosis terminals.</p>",
        render_mermaid_block(mm, caption=f"Diagnostic decision tree — {tree.code}"),
    ]
    return "\n".join(bits)


def render_model_pathway(
    tree,
    pathway: PathwayResult,
    model: str,
    gates: dict | None = None,
) -> str:
    """Per-model pathway as HTML step list only (no Mermaid — keeps matrix fast)."""
    badge = "neval"
    if pathway.not_evaluated:
        badge = "neval"
    elif pathway.present:
        badge = "present"
    else:
        badge = "absent"

    parts = [
        f'<div class="model-path" data-model="{_esc(model)}">',
        f'<div class="path-head">'
        f"<strong>{_esc(model)}</strong> "
        f'<span class="badge {badge}">{_esc(pathway.terminal_label)}</span>'
        f"</div>",
        '<details class="evidence-details"><summary>Step log + trajectory evidence</summary>',
        '<ol class="path-steps">',
    ]

    for i, step in enumerate(pathway.steps, 1):
        cls = f"step {step.kind}"
        if step.branch == "yes":
            cls += " took-yes"
        elif step.branch == "no":
            cls += " took-no"
        if step.kind == "terminal":
            cls += " " + badge

        gate_html = ""
        # show all metrics touched at this step
        mids = []
        if step.metric_id:
            mids.append(step.metric_id)
        for snip in step.evidence_snippets:
            if ":" in snip and not snip.startswith(" "):
                mid = snip.split(":", 1)[0].strip()
                if mid and mid not in mids and " " not in mid:
                    mids.append(mid)
        if gates:
            chips = []
            for mid in mids:
                g = gates.get(mid)
                if not g:
                    continue
                pr = f"{g.pass_rate:.0%}" if g.pass_rate is not None else "?"
                st = f"{g.std:.2f}" if g.std is not None else "?"
                chips.append(
                    f'<div class="gate-chip {status_class(g.status)}">'
                    f"<code>{_esc(g.metric_id)}</code> "
                    f"{_esc(g.status)} · pr={_esc(pr)} · σ={_esc(st)}"
                    f"</div>"
                )
            gate_html = "".join(chips)

        branch_html = ""
        if step.branch:
            ans = "YES" if step.branch == "yes" else "NO"
            branch_html = f' <span class="branch-taken {step.branch}">→ {ans}</span>'

        evid = ""
        if step.evidence_snippets:
            items = "".join(f"<li>{_esc(s)}</li>" for s in step.evidence_snippets[:6])
            evid = f'<ul class="evidence">{items}</ul>'

        parts.append(
            f'<li class="{cls}">'
            f'<div class="step-label"><span class="n">{i}.</span> '
            f"{_esc(step.label)}{branch_html}</div>"
            f"{gate_html}{evid}"
            f"</li>"
        )

    parts.append("</ol></details></div>")
    return "\n".join(parts)


def render_syndrome_section(
    code: str,
    models: list[str],
    by_model: dict[str, dict[str, Any]],
) -> str:
    tree = SYNDROME_TREES.get(code)
    if not tree:
        # finding without tree def
        name = code
        for m in models:
            f = by_model[m]["findings"].get(code)
            if f and f.get("name"):
                name = f"{code} — {f['name']}"
                break
        return (
            f'<details class="syndrome" id="syndrome-{_esc(code)}">'
            f"<summary><strong>{_esc(name)}</strong> "
            f"<em>(no formal decision tree yet)</em></summary>"
            f"<p>Finding exists in reports but has no tree in "
            f"<code>decision_trees.py</code>.</p></details>"
        )

    # matrix row summary chips
    chips = []
    pathways: dict[str, PathwayResult] = {}
    for m in models:
        gates = gates_from_report_acc(by_model[m])
        pw = evaluate_tree(tree, gates)
        pathways[m] = pw
        if pw.not_evaluated:
            chips.append(f'<span class="chip neval">{_esc(m)}: N/E</span>')
        elif pw.present:
            chips.append(
                f'<span class="chip present">{_esc(m)}: PRESENT/{_esc(pw.severity)}</span>'
            )
        else:
            chips.append(f'<span class="chip absent">{_esc(m)}: absent</span>')

    body = [
        # Always collapsed by default (user expands as needed)
        f'<details class="syndrome" id="syndrome-{_esc(code)}">',
        f"<summary>"
        f"<strong>{_esc(tree.code)}</strong> — {_esc(tree.name)} "
        f'<span class="chips">{"".join(chips)}</span>'
        f"</summary>",
        '<div class="syndrome-body">',
        f'<p class="algo-note">Clinical decision algorithm as a <strong>directed Mermaid graph</strong> '
        f"(lazy-loaded when this section opens). "
        f"Sub-criteria fan into diamonds; Yes/No edges lead to severity terminals.</p>",
        render_reference_flowchart(tree),
        "<h3>Per-model diagnosis pathway + trajectory evidence</h3>",
        "<p>Pathways use a compact step log (not per-model flowcharts) so the report "
        "stays interactive. Expand “Step log” for gates and trajectory evidence.</p>",
    ]
    for m in models:
        gates = gates_from_report_acc(by_model[m])
        body.append(render_model_pathway(tree, pathways[m], m, gates=gates))
    body.append("</div></details>")
    return "\n".join(body)


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
            cells.append(
                "<td class='pass'>RUN</td>" if ran else "<td class='not-run'>NOT RUN</td>"
            )
        pack_rows.append(
            f"<tr><th class='row'>{html.escape(pack)}</th>{''.join(cells)}</tr>"
        )

    # gates matrix
    gate_rows = []
    for metric in metrics:
        cite_ids = citations_for_metric(metric)
        if cite_ids:
            cite_html = (
                '<sup class="cites">['
                + ",".join(
                    f'<a class="cite" href="#ref-{i}">{i}</a>'
                    for i in sorted(set(cite_ids))
                )
                + "]</sup>"
            )
            metric_label = f"<code>{html.escape(metric)}</code> {cite_html}"
        else:
            metric_label = f"<code>{html.escape(metric)}</code>"
        cells = []
        for m in models:
            text, cls = fmt_gate_cell(by_model[m]["gates"].get(metric))
            title_attr = ""
            g = by_model[m]["gates"].get(metric)
            if g and g.get("explanation"):
                title_attr = f' title="{html.escape(str(g["explanation"])[:400])}"'
            cells.append(f"<td class='{cls}'{title_attr}>{html.escape(text)}</td>")
        gate_rows.append(
            f"<tr><th class='row metric'>{metric_label}</th>{''.join(cells)}</tr>"
        )

    # findings matrix
    finding_rows = []
    for code in finding_codes:
        name = code
        tree = SYNDROME_TREES.get(code)
        if tree:
            name = f"{code} — {tree.name}"
        else:
            for m in models:
                f = by_model[m]["findings"].get(code)
                if f and f.get("name"):
                    name = f"{code} — {f['name']}"
                    break
        cells = []
        for m in models:
            # prefer live finding; fall back to tree eval
            f = by_model[m]["findings"].get(code)
            if f is None and tree is not None:
                pw = evaluate_tree(tree, gates_from_report_acc(by_model[m]))
                if pw.not_evaluated:
                    text, cls = "NOT RUN", "not-run"
                elif pw.present:
                    text, cls = f"PRESENT · {pw.severity}", "present"
                else:
                    text, cls = f"absent · {pw.severity}", "absent"
                title_attr = f' title="{html.escape(pw.terminal_label)}"'
            else:
                text, cls = fmt_finding_cell(f)
                title_attr = ""
                if f and f.get("rationale"):
                    title_attr = f' title="{html.escape(str(f["rationale"])[:400])}"'
            link = f"#syndrome-{html.escape(code)}"
            cells.append(
                f"<td class='{cls}'{title_attr}>"
                f"<a class='cell-link' href='{link}'>{html.escape(text)}</a></td>"
            )
        finding_rows.append(
            f"<tr><th class='row'><a href='#syndrome-{html.escape(code)}'>"
            f"{html.escape(name)}</a></th>{''.join(cells)}</tr>"
        )

    # expandable decision trees — catalogue order then any extras
    tree_order = list(SYNDROME_TREES.keys())
    for c in finding_codes:
        if c not in tree_order:
            tree_order.append(c)
    syndrome_sections = "\n".join(
        render_syndrome_section(code, models, by_model) for code in tree_order
    )

    # references
    refs_map = references_used(metrics)
    ref_items = []
    for num, meta in refs_map.items():
        url = meta.get("url") or ""
        text = meta.get("text") or meta.get("short") or str(num)
        if url:
            body = f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(text)}</a>'
        else:
            body = html.escape(text)
        ref_items.append(f'<li id="ref-{num}">[{num}] {body}</li>')
    refs_html = (
        "\n".join(ref_items)
        if ref_items
        else "<li>No survey citations mapped for these metrics.</li>"
    )

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
  body {{
    margin: 0; padding: 10px 14px;
    font: 13px/1.35 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: #fff; color: #111;
  }}
  h1 {{ margin: 0 0 4px; font-size: 1.2rem; }}
  h2 {{ margin: 16px 0 6px; font-size: 1.05rem; }}
  h3 {{ margin: 12px 0 6px; font-size: 0.95rem; }}
  p, .meta {{ margin: 0 0 6px; color: #444; font-size: 12px; }}
  .legend {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 8px; font-size: 12px; }}
  .legend span {{ display: inline-flex; align-items: center; gap: 4px; }}
  .swatch {{ width: 10px; height: 10px; border: 1px solid #999; display: inline-block; }}
  .swatch.pass, td.pass {{ background: #c8e6c9; }}
  .swatch.fail, td.fail {{ background: #ffcdd2; }}
  .swatch.unstable, td.unstable {{ background: #fff3cd; }}
  .swatch.not-run, td.not-run {{ background: #eee; color: #555; font-style: italic; }}
  .swatch.present, td.present {{ background: #ffcdd2; }}
  .swatch.absent, td.absent {{ background: #c8e6c9; }}
  .panel {{ border: 1px solid #ccc; overflow: auto; margin: 0 0 6px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 12px; }}
  th, td {{ border: 1px solid #ccc; padding: 2px 5px; text-align: center; vertical-align: middle; }}
  th.model, th.corner {{ position: sticky; top: 0; background: #f5f5f5; z-index: 2; }}
  th.corner {{ left: 0; z-index: 3; text-align: left; }}
  th.row {{
    position: sticky; left: 0; background: #fafafa; text-align: left;
    z-index: 1; font-weight: 600; max-width: 320px;
  }}
  th.row.metric {{ font-size: 13px; }}
  th.row.metric code {{ font-size: 13px; }}
  td {{ font-variant-numeric: tabular-nums; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
  a {{ color: #0645ad; }}
  a:hover {{ text-decoration: underline; }}
  a.cell-link {{ color: inherit; text-decoration: none; }}
  a.cell-link:hover {{ text-decoration: underline; }}
  sup.cites {{ margin-left: 2px; white-space: nowrap; font-size: 0.9em; }}
  a.cite {{ color: #0645ad; text-decoration: none; }}
  .refs {{ margin: 0 0 6px; }}
  .refs ul {{ margin: 0; padding-left: 1.2em; list-style: disc; font-size: 12px; }}
  .refs li {{ margin: 0 0 2px; }}
  .refs li:target {{ background: #fff3cd; }}
  footer {{ margin-top: 12px; color: #666; font-size: 11px; }}
  ul.sources {{ margin: 0; padding-left: 1.2em; font-size: 12px; }}

  /* expandable syndromes */
  details.syndrome {{
    border: 1px solid #ccc; margin: 0 0 8px; padding: 0;
    background: #fff;
  }}
  details.syndrome > summary {{
    cursor: pointer; padding: 6px 8px; background: #f7f7f7;
    font-size: 13px; list-style: none;
  }}
  details.syndrome > summary::-webkit-details-marker {{ display: none; }}
  details.syndrome > summary::before {{
    content: "▸ "; color: #666; font-weight: 700;
  }}
  details.syndrome[open] > summary::before {{ content: "▾ "; }}
  details.syndrome[open] > summary {{ border-bottom: 1px solid #ddd; }}
  .syndrome-body {{ padding: 8px 10px 10px; }}
  .chips {{ display: inline-flex; flex-wrap: wrap; gap: 4px; margin-left: 8px; }}
  .chip {{
    font-size: 11px; font-weight: 500; padding: 1px 6px;
    border: 1px solid #bbb; border-radius: 3px; background: #fff;
  }}
  .chip.present {{ background: #ffcdd2; border-color: #e57373; }}
  .chip.absent {{ background: #c8e6c9; border-color: #81c784; }}
  .chip.neval {{ background: #eee; color: #555; }}

  .flow-title {{ font-weight: 700; margin: 0 0 4px; font-size: 12px; }}
  .flow-desc, .flow-metrics, .algo-note {{ font-size: 12px; color: #444; margin: 0 0 6px; }}
  .mermaid-wrap {{
    border: 1px solid #ccc; background: #fafafa; padding: 8px 10px;
    margin: 0 0 12px; overflow-x: auto; min-height: 0;
  }}
  .mermaid-host {{ text-align: center; }}
  .mermaid-host svg {{ max-width: 100%; height: auto; }}
  pre.mermaid-fallback {{
    margin: 0; background: transparent; border: none;
    font-size: 11px; text-align: left; white-space: pre-wrap;
  }}
  .mermaid-loading {{ font-size: 12px; color: #666; padding: 8px 0; }}
  /* per-model path */
  .model-path {{
    border: 1px solid #ddd; margin: 0 0 10px; padding: 6px 8px;
    background: #fff;
  }}
  .path-head {{ margin-bottom: 4px; font-size: 12px; }}
  .badge {{
    display: inline-block; padding: 1px 6px; border: 1px solid #999;
    border-radius: 3px; font-size: 11px; font-weight: 600;
  }}
  .badge.present {{ background: #ffcdd2; }}
  .badge.absent {{ background: #c8e6c9; }}
  .badge.neval {{ background: #eee; }}
  details.evidence-details {{ margin-top: 4px; font-size: 12px; }}
  details.evidence-details > summary {{ cursor: pointer; color: #0645ad; }}
  ol.path-steps {{ margin: 4px 0 0; padding-left: 18px; }}
  ol.path-steps li {{ margin: 0 0 6px; font-size: 12px; }}
  ol.path-steps li.took-yes {{ border-left: 3px solid #c62828; padding-left: 6px; }}
  ol.path-steps li.took-no {{ border-left: 3px solid #2e7d32; padding-left: 6px; }}
  ol.path-steps li.terminal {{ font-weight: 600; }}
  .step-label .n {{ color: #666; margin-right: 2px; }}
  .branch-taken {{ font-weight: 700; font-size: 11px; }}
  .branch-taken.yes {{ color: #b71c1c; }}
  .branch-taken.no {{ color: #1b5e20; }}
  .gate-chip {{
    display: inline-block; margin: 2px 0; padding: 1px 5px;
    border: 1px solid #ccc; font-size: 11px;
  }}
  .gate-chip.pass {{ background: #c8e6c9; }}
  .gate-chip.fail {{ background: #ffcdd2; }}
  .gate-chip.unstable {{ background: #fff3cd; }}
  ul.evidence {{
    margin: 2px 0 0 0; padding-left: 16px; color: #333; font-size: 11px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  }}
  .toc {{ font-size: 12px; margin: 0 0 10px; }}
  .toc a {{ margin-right: 8px; }}
</style>
</head>
<body>
  <h1>{html.escape(title)}</h1>
  <div class="meta">
    Generated {html.escape(generated)} ·
    {len(models)} model(s) ·
    {len(packs)} pack(s) ·
    {len(metrics)} metric(s) ·
    {len(finding_codes)} syndrome(s) ·
    decision trees: {len(SYNDROME_TREES)}
  </div>
  <div class="legend">
    <span><i class="swatch pass"></i> PASS / RUN / absent</span>
    <span><i class="swatch fail"></i> FAIL / PRESENT</span>
    <span><i class="swatch unstable"></i> UNSTABLE</span>
    <span><i class="swatch not-run"></i> NOT RUN</span>
  </div>
  <p class="algo-note">
    Syndrome cells link to expandable <strong>diagnostic decision trees</strong>
    (clinical yes/no algorithm + per-model pathway with trajectory evidence).
    Trees formalize the polythetic rules in <code>criteria.py</code>.
  </p>

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

  <h2 id="syndrome-matrix">Syndrome matrix</h2>
  <p>
    Composite diagnoses. Click a cell or syndrome name to jump to its
    expandable decision tree (algorithm + per-model pathway evidence).
  </p>
  <div class="panel">
    <table>
      <thead><tr><th class="corner">Syndrome</th>{th_models()}</tr></thead>
      <tbody>
        {''.join(finding_rows) if finding_rows else '<tr><td colspan="99">No findings found</td></tr>'}
      </tbody>
    </table>
  </div>

  <h2 id="decision-trees">Diagnostic decision trees (expandable)</h2>
  <p>
    Each section is a full clinical-style decision algorithm (diamonds = criteria,
    terminals = diagnosis). Open a syndrome to see the reference tree and the
    exact pathway taken for every benchmarked model, with gate stats and
    trajectory evidence snippets.
  </p>
  <div class="toc">
    Jump:
    {" ".join(f'<a href="#syndrome-{html.escape(c)}">{html.escape(c)}</a>' for c in tree_order)}
  </div>
  {syndrome_sections}

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

  <h2>References</h2>
  <p>Survey sources for outcome-gate metrics (<code>sources/bibliography.md</code>). Click <code>[n]</code> in the Metric column to jump here.</p>
  <div class="refs">
    <ul>
      {refs_html}
    </ul>
  </div>

  <h2>Sources (run artifacts)</h2>
  <ul class="sources">
    {''.join(source_blocks)}
  </ul>

  <footer>
    DSM-AE HTML report · Mermaid decision graphs (lazy-loaded on expand) from
    criteria.py / decision_trees.py · NOT RUN = missing pack coverage ·
    generated from diagnosis JSON (gates + bootstraps + findings)
  </footer>
  <script>
  (function () {{
    // Performance: do NOT load mermaid or render any SVG until a syndrome
    // section is opened. Sources live in <script type="text/plain"> so
    // startOnLoad cannot process hundreds of graphs on first paint.
    const MERMAID_CDN = "https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js";
    let mermaidLoading = null;
    let mermaidReady = false;

    function loadMermaid() {{
      if (mermaidReady && window.mermaid) return Promise.resolve(window.mermaid);
      if (mermaidLoading) return mermaidLoading;
      mermaidLoading = new Promise((resolve, reject) => {{
        const s = document.createElement("script");
        s.src = MERMAID_CDN;
        s.async = true;
        s.onload = () => {{
          try {{
            window.mermaid.initialize({{
              startOnLoad: false,
              theme: "neutral",
              securityLevel: "loose",
              flowchart: {{ htmlLabels: true, curve: "basis", useMaxWidth: true }}
            }});
            mermaidReady = true;
            resolve(window.mermaid);
          }} catch (e) {{ reject(e); }}
        }};
        s.onerror = () => reject(new Error("Failed to load mermaid.js"));
        document.head.appendChild(s);
      }});
      return mermaidLoading;
    }}

    async function renderLazyIn(root) {{
      const wraps = root.querySelectorAll
        ? root.querySelectorAll("[data-lazy-mermaid]:not([data-rendered])")
        : [];
      if (!wraps.length) return;
      wraps.forEach((w) => {{
        const host = w.querySelector(".mermaid-host");
        if (host) {{
          host.hidden = false;
          host.innerHTML = '<div class="mermaid-loading">Loading diagram…</div>';
        }}
      }});
      let m;
      try {{
        m = await loadMermaid();
      }} catch (e) {{
        wraps.forEach((w) => {{
          const host = w.querySelector(".mermaid-host");
          if (host) host.textContent = "Diagram library failed to load.";
        }});
        return;
      }}
      const nodes = [];
      wraps.forEach((w) => {{
        const srcEl = w.querySelector("script.mermaid-src");
        const host = w.querySelector(".mermaid-host");
        if (!srcEl || !host) return;
        const pre = document.createElement("pre");
        pre.className = "mermaid";
        pre.textContent = srcEl.textContent || "";
        host.innerHTML = "";
        host.appendChild(pre);
        nodes.push(pre);
        w.setAttribute("data-rendered", "1");
      }});
      if (nodes.length) {{
        try {{
          await m.run({{ nodes }});
        }} catch (e) {{
          console.warn("mermaid.run failed", e);
        }}
      }}
    }}

    document.querySelectorAll("details.syndrome").forEach((d) => {{
      d.addEventListener("toggle", () => {{
        if (d.open) renderLazyIn(d);
      }});
      // If somehow open on load (hash jump), render then
      if (d.open) renderLazyIn(d);
    }});

    // Hash navigation: open target syndrome and render its diagram only
    function openHash() {{
      if (!location.hash) return;
      const el = document.querySelector(location.hash);
      if (el && el.tagName === "DETAILS") {{
        el.open = true;
        renderLazyIn(el);
      }}
    }}
    window.addEventListener("hashchange", openHash);
    openHash();
  }})();
  </script>
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
    print(f"  decision trees: {len(SYNDROME_TREES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
