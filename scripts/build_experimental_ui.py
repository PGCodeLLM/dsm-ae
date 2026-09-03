#!/usr/bin/env python3
"""Build experimental Comparison UIs: semantic metric groups + gel fingerprints.

Writes under reports/experimental-ui/:
  index.html          — gallery of 5 visual variants
  v1-gel-classic.html
  v2-coomassie.html
  v3-silver-stain.html
  v4-lane-scan.html
  v5-family-chroma.html

Each variant:
  - Orders metric rows by semantic proximity (multi-agent block, tools, …)
  - Orders model columns by fingerprint similarity (correlation of pass rates)
  - Renders pass rates as electrophoresis-like band intensity

Usage:
  PYTHONPATH=src python3 scripts/build_experimental_ui.py
  PYTHONPATH=src python3 scripts/build_experimental_ui.py --out reports/experimental-ui
"""

from __future__ import annotations

import argparse
import html
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from experimental_metric_layout import ordered_metrics, ordered_syndromes  # noqa: E402
from json_to_html_report import (  # noqa: E402
    collect_universe_fixed,
    discover_jsons,
    load_report,
    merge_reports,
    model_id,
)


def _pass_rate(by_model: dict, model: str, metric: str) -> float | None:
    g = by_model[model]["gates"].get(metric)
    if not g:
        return None
    pr = g.get("pass_rate")
    if pr is None:
        return None
    try:
        return max(0.0, min(1.0, float(pr)))
    except Exception:
        return None


def _finding_score(by_model: dict, model: str, code: str) -> float | None:
    """Map finding to gel intensity: absent=1 (healthy band), present=0, missing=None."""
    f = by_model[model]["findings"].get(code)
    if not f:
        return None
    if f.get("present"):
        sev = str(f.get("severity") or "moderate").lower()
        return {"critical": 0.0, "severe": 0.15, "moderate": 0.35, "mild": 0.55}.get(
            sev, 0.3
        )
    return 1.0


def _fingerprint_vectors(
    models: list[str], metrics: list[str], by_model: dict
) -> dict[str, list[float]]:
    """Pass-rate vector per model; missing → 0.5 (neutral)."""
    vecs: dict[str, list[float]] = {}
    for m in models:
        v = []
        for metric in metrics:
            pr = _pass_rate(by_model, m, metric)
            v.append(0.5 if pr is None else pr)
        vecs[m] = v
    return vecs


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    if n < 2:
        return 0.0
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da < 1e-12 or db < 1e-12:
        return 0.0
    return num / (da * db)


def order_models_by_similarity(
    models: list[str], metrics: list[str], by_model: dict
) -> list[str]:
    """Greedy nearest-neighbour ordering so similar fingerprints sit adjacent."""
    if len(models) <= 2:
        return list(models)
    vecs = _fingerprint_vectors(models, metrics, by_model)
    # start with model farthest from mean (most distinctive)
    mean = [sum(vecs[m][i] for m in models) / len(models) for i in range(len(metrics))]
    start = max(models, key=lambda m: sum((a - b) ** 2 for a, b in zip(vecs[m], mean)))
    ordered = [start]
    remaining = set(models) - {start}
    while remaining:
        last = ordered[-1]
        nxt = max(remaining, key=lambda m: _pearson(vecs[last], vecs[m]))
        ordered.append(nxt)
        remaining.remove(nxt)
    return ordered


# ---------------------------------------------------------------------------
# Theme definitions: map pass_rate t∈[0,1] (+ missing) → CSS background
# ---------------------------------------------------------------------------

Theme = dict[str, Any]


THEMES: list[Theme] = [
    {
        "id": "v1-gel-classic",
        "name": "Gel classic (ethidium)",
        "blurb": "Dark agarose gel · bright orange–pink bands where capability is high · black voids = not run.",
        "page_bg": "#0a0a0c",
        "page_fg": "#e8e4dc",
        "panel_bg": "#121218",
        "header_bg": "#1a1a22",
        "row_bg": "#0e0e14",
        "group_bg": "#1c1520",
        "group_fg": "#f0a060",
        "border": "#2a2430",
        "accent": "#ff6b3d",
        "cell_fn": "ethidium",
        "show_text": False,
    },
    {
        "id": "v2-coomassie",
        "name": "Coomassie blue",
        "blurb": "Protein-gel aesthetic · deep blue bands on pale field · stronger stain = higher pass rate.",
        "page_bg": "#f4f1ea",
        "page_fg": "#1a1a2e",
        "panel_bg": "#fffef9",
        "header_bg": "#e8e4f0",
        "row_bg": "#faf8f4",
        "group_bg": "#dce6f5",
        "group_fg": "#1a3a6e",
        "border": "#9aa8c0",
        "accent": "#244a9b",
        "cell_fn": "coomassie",
        "show_text": True,
    },
    {
        "id": "v3-silver-stain",
        "name": "Silver stain",
        "blurb": "Greyscale densitometry · dark silver deposits = high pass · faint = fragile · empty = missing.",
        "page_bg": "#ebe8e4",
        "page_fg": "#222",
        "panel_bg": "#f7f5f2",
        "header_bg": "#ddd9d4",
        "row_bg": "#f2efeb",
        "group_bg": "#d0ccc6",
        "group_fg": "#111",
        "border": "#aaa59e",
        "accent": "#444",
        "cell_fn": "silver",
        "show_text": True,
    },
    {
        "id": "v4-lane-scan",
        "name": "Lane densitometry",
        "blurb": "Each model is a gel lane · continuous heat along the column · group separators like molecular-weight markers.",
        "page_bg": "#0d1117",
        "page_fg": "#c9d1d9",
        "panel_bg": "#010409",
        "header_bg": "#161b22",
        "row_bg": "#0d1117",
        "group_bg": "#21262d",
        "group_fg": "#58a6ff",
        "border": "#30363d",
        "accent": "#3fb950",
        "cell_fn": "viridis",
        "show_text": False,
    },
    {
        "id": "v5-family-chroma",
        "name": "Family chroma + gel",
        "blurb": "Same gel intensity, tinted by model family (GPT / Claude / Qwen / …) so lineage fingerprints pop.",
        "page_bg": "#0f0f12",
        "page_fg": "#ece8e1",
        "panel_bg": "#14141a",
        "header_bg": "#1e1e28",
        "row_bg": "#12121a",
        "group_bg": "#252033",
        "group_fg": "#c4b5fd",
        "border": "#333344",
        "accent": "#a78bfa",
        "cell_fn": "family",
        "show_text": False,
    },
]


def _family(model: str) -> str:
    m = model.lower()
    if m.startswith("gpt-") or "gpt" in m:
        return "gpt"
    if m.startswith("claude"):
        return "claude"
    if m.startswith("qwen"):
        return "qwen"
    if m.startswith("glm"):
        return "glm"
    if m.startswith("deepseek"):
        return "deepseek"
    if m.startswith("grok"):
        return "grok"
    return "other"


_FAMILY_HUE = {
    "gpt": 200,
    "claude": 25,
    "qwen": 280,
    "glm": 160,
    "deepseek": 320,
    "grok": 120,
    "other": 0,
}


def cell_style(
    theme: Theme, t: float | None, *, model: str = "", mode: str = "metric"
) -> tuple[str, str]:
    """Return (css_style, display_text_hint). t=None → not run."""
    fn = theme["cell_fn"]
    if t is None:
        if fn in ("ethidium", "viridis", "family"):
            return "background:#050508;color:#333", "—"
        if fn == "coomassie":
            return "background:#f0ebe3;color:#bbb", "—"
        return "background:#e8e4de;color:#aaa", "—"

    t = max(0.0, min(1.0, float(t)))
    pct = f"{int(round(t * 100))}%"

    if fn == "ethidium":
        # black → deep red → hot orange/pink
        r = int(20 + t * 235)
        g = int(5 + t * 80)
        b = int(10 + t * 40)
        glow = f"0 0 {int(4 + t * 10)}px rgba(255,{int(80+t*100)},40,{0.15+t*0.55})"
        return (
            f"background:rgb({r},{g},{b});color:#fff;box-shadow:inset 0 0 0 1px rgba(255,200,100,{0.1+t*0.3}),{glow}",
            pct,
        )

    if fn == "coomassie":
        # pale → coomassie blue
        r = int(245 - t * 200)
        g = int(248 - t * 180)
        b = int(255 - t * 80)
        fg = "#111" if t < 0.55 else "#fff"
        return f"background:rgb({r},{g},{b});color:{fg}", pct

    if fn == "silver":
        # light field, dark silver deposit for high pass
        v = int(240 - t * 200)
        fg = "#111" if v > 120 else "#f5f5f5"
        return f"background:rgb({v},{v},{int(v*0.98)});color:{fg}", pct

    if fn == "viridis":
        # approx viridis
        stops = [
            (68, 1, 84),
            (59, 82, 139),
            (33, 145, 140),
            (94, 201, 98),
            (253, 231, 37),
        ]
        x = t * (len(stops) - 1)
        i = int(x)
        f = x - i
        if i >= len(stops) - 1:
            r, g, b = stops[-1]
        else:
            r = int(stops[i][0] * (1 - f) + stops[i + 1][0] * f)
            g = int(stops[i][1] * (1 - f) + stops[i + 1][1] * f)
            b = int(stops[i][2] * (1 - f) + stops[i + 1][2] * f)
        fg = "#fff" if t < 0.65 else "#111"
        return f"background:rgb({r},{g},{b});color:{fg}", pct

    if fn == "family":
        hue = _FAMILY_HUE.get(_family(model), 0)
        # lightness by pass rate; saturation fixed
        light = 12 + t * 48
        sat = 55 + t * 35
        fg = "#fff" if light < 45 else "#111"
        return (
            f"background:hsl({hue} {sat}% {light}%);color:{fg}",
            pct,
        )

    return "", pct


def build_variant_html(
    theme: Theme,
    *,
    by_model: dict[str, dict[str, Any]],
    models: list[str],
    metrics: list[str],
    finding_codes: list[str],
    generated: str,
) -> str:
    metric_rows = ordered_metrics(metrics)
    syndrome_codes = ordered_syndromes(finding_codes)
    # fingerprints only on non-header metrics
    metric_ids = [m for _, lab, m in metric_rows if m]
    models = order_models_by_similarity(models, metric_ids, by_model)

    # precompute styles
    def th_models() -> str:
        parts = []
        for i, m in enumerate(models):
            fam = _family(m)
            parts.append(
                f"<th class='model fam-{html.escape(fam)}' data-model-col='{i}' "
                f"data-model='{html.escape(m, quote=True)}' title='{html.escape(m)}'>"
                f"<span class='mshort'>{html.escape(_short_model(m))}</span>"
                f"<span class='mfull'>{html.escape(m)}</span></th>"
            )
        return "".join(parts)

    # metric table body
    body_metric: list[str] = []
    for gid, glabel, mid in metric_rows:
        if glabel is not None and mid == "":
            body_metric.append(
                f"<tr class='group-row' data-group='{html.escape(gid or '')}'>"
                f"<th class='group-label' colspan='{1 + len(models)}'>"
                f"{html.escape(glabel)}</th></tr>"
            )
            continue
        cells = []
        for i, m in enumerate(models):
            pr = _pass_rate(by_model, m, mid)
            style, tip = cell_style(theme, pr, model=m)
            label = tip if theme.get("show_text") else ""
            tip_attr = html.escape(
                f"{m} · {mid} · {tip if pr is not None else 'not run'}", quote=True
            )
            cells.append(
                f"<td class='band' data-model-col='{i}' data-model='{html.escape(m, quote=True)}' "
                f"data-tip='{tip_attr}' style='{style}'>{html.escape(label)}</td>"
            )
        body_metric.append(
            f"<tr class='metric-row' data-group='{html.escape(gid or '')}'>"
            f"<th class='row metric'><code>{html.escape(mid)}</code></th>"
            f"{''.join(cells)}</tr>"
        )

    # syndrome body
    body_syn: list[str] = []
    for code in syndrome_codes:
        cells = []
        for i, m in enumerate(models):
            sc = _finding_score(by_model, m, code)
            style, tip = cell_style(theme, sc, model=m, mode="finding")
            f = by_model[m]["findings"].get(code)
            if f is None:
                text = "—" if theme.get("show_text") else ""
                tip_s = f"{m} · {code} · not run"
            elif f.get("present"):
                text = (f.get("severity") or "P")[:4] if theme.get("show_text") else ""
                tip_s = f"{m} · {code} · PRESENT · {f.get('severity')}"
            else:
                text = "ok" if theme.get("show_text") else ""
                tip_s = f"{m} · {code} · not present"
            cells.append(
                f"<td class='band' data-model-col='{i}' data-tip='{html.escape(tip_s, quote=True)}' "
                f"style='{style}'>{html.escape(text)}</td>"
            )
        body_syn.append(
            f"<tr><th class='row'><code>{html.escape(code)}</code></th>{''.join(cells)}</tr>"
        )

    # model filter
    filter_items = []
    for i, m in enumerate(models):
        filter_items.append(
            f'<label class="mf-item"><input type="checkbox" class="model-col-toggle" '
            f'data-model-col="{i}" data-model="{html.escape(m, quote=True)}" checked/> '
            f"<code>{html.escape(_short_model(m))}</code></label>"
        )

    t = theme
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="{html.escape(t['id'])}">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{html.escape(t['name'])} · DSM-AE experimental</title>
<style>
  :root {{
    --bg: {t['page_bg']}; --fg: {t['page_fg']}; --panel: {t['panel_bg']};
    --header: {t['header_bg']}; --row: {t['row_bg']}; --group: {t['group_bg']};
    --group-fg: {t['group_fg']}; --border: {t['border']}; --accent: {t['accent']};
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 12px 16px 40px;
    font: 13px/1.4 ui-sans-serif, system-ui, Segoe UI, Roboto, sans-serif;
    background: var(--bg); color: var(--fg);
  }}
  a {{ color: var(--accent); }}
  h1 {{ margin: 0 0 4px; font-size: 1.25rem; font-weight: 650; letter-spacing: 0.02em; }}
  h2 {{ margin: 18px 0 8px; font-size: 1rem; color: var(--accent); }}
  .meta {{ color: color-mix(in srgb, var(--fg) 70%, transparent); font-size: 12px; margin: 0 0 8px; }}
  .blurb {{
    max-width: 72rem; margin: 0 0 12px; padding: 8px 10px;
    border-left: 3px solid var(--accent); background: var(--panel); font-size: 12.5px;
  }}
  .nav {{
    display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 12px; align-items: center;
  }}
  .nav a {{
    display: inline-block; padding: 4px 10px; border: 1px solid var(--border);
    border-radius: 999px; text-decoration: none; font-size: 12px;
    background: var(--panel); color: var(--fg);
  }}
  .nav a:hover {{ border-color: var(--accent); }}
  .nav a.active {{ background: var(--accent); color: #111; border-color: var(--accent); font-weight: 600; }}
  .model-filter {{
    border: 1px solid var(--border); background: var(--panel); margin: 0 0 12px;
    padding: 8px 10px; border-radius: 6px;
  }}
  .model-filter > summary {{ cursor: pointer; font-weight: 600; font-size: 12.5px; }}
  .model-filter-actions {{ display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }}
  .model-filter-actions button {{
    font: inherit; font-size: 12px; padding: 2px 8px; cursor: pointer;
    border: 1px solid var(--border); border-radius: 3px; background: var(--bg); color: var(--fg);
  }}
  .model-filter-grid {{ display: flex; flex-wrap: wrap; gap: 4px 12px; max-height: 160px; overflow-y: auto; }}
  .mf-item {{ display: inline-flex; align-items: center; gap: 4px; font-size: 12px; cursor: pointer; }}
  .panel {{
    border: 1px solid var(--border); background: var(--panel);
    overflow-x: auto; margin: 0 0 16px; border-radius: 4px;
  }}
  table {{
    border-collapse: separate; border-spacing: 0;
    width: max-content; min-width: 100%; font-size: 11px;
  }}
  th, td {{
    border: 1px solid var(--border); padding: 0;
    text-align: center; vertical-align: middle;
  }}
  thead th {{
    position: sticky; top: 0; z-index: 3;
    background: var(--header); padding: 6px 4px;
    box-shadow: 0 1px 0 var(--border);
    writing-mode: vertical-rl; transform: rotate(180deg);
    max-height: 140px; font-size: 10px; font-weight: 600;
  }}
  th.corner {{
    position: sticky; left: 0; top: 0; z-index: 5;
    writing-mode: horizontal-tb; transform: none;
    text-align: left; padding: 6px 8px; min-width: 200px;
    background: var(--header);
  }}
  th.row {{
    position: sticky; left: 0; z-index: 2;
    background: var(--row); text-align: left; padding: 3px 8px;
    font-weight: 500; max-width: 280px; box-shadow: 1px 0 0 var(--border);
  }}
  th.row.metric code {{ font-size: 11px; }}
  th.group-label {{
    text-align: left; padding: 6px 10px; background: var(--group); color: var(--group-fg);
    font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase;
    position: sticky; left: 0; z-index: 2;
  }}
  td.band {{
    width: 28px; min-width: 28px; height: 18px;
    font-size: 9px; font-variant-numeric: tabular-nums;
  }}
  th.model .mfull {{ display: none; }}
  th.model:hover .mshort {{ display: none; }}
  th.model:hover .mfull {{ display: inline; }}
  th.model.col-hidden, td.col-hidden, .mf-item.col-hidden {{ display: none !important; }}
  .legend-gel {{
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
    font-size: 11px; margin: 0 0 10px; color: color-mix(in srgb, var(--fg) 75%, transparent);
  }}
  .legend-gel .bar {{
    width: 160px; height: 12px; border-radius: 2px; border: 1px solid var(--border);
  }}
  #cell-tip {{
    position: fixed; z-index: 10000; max-width: 320px; padding: 6px 8px;
    border: 1px solid var(--border); border-radius: 4px;
    background: #111; color: #f5f5f5; font: 11px/1.4 ui-monospace, monospace;
    white-space: pre-line; pointer-events: none; opacity: 0; visibility: hidden;
    box-shadow: 0 4px 14px rgba(0,0,0,0.4);
  }}
  #cell-tip.visible {{ opacity: 1; visibility: visible; }}
  footer {{ margin-top: 20px; font-size: 11px; opacity: 0.7; }}
</style>
</head>
<body>
  <div class="nav">
    <a href="index.html">Gallery</a>
    {_nav_links(t['id'])}
  </div>
  <h1>{html.escape(t['name'])}</h1>
  <p class="meta">Generated {html.escape(generated)} · {len(models)} models (similarity-ordered) ·
    {len(metric_ids)} metrics in semantic groups · experimental · not production matrix</p>
  <p class="blurb">{html.escape(t['blurb'])}</p>
  <div class="legend-gel">
    <span>Fingerprint intensity</span>
    <span>low / disordered</span>
    <i class="bar" style="{_legend_bar(theme)}"></i>
    <span>high / attuned</span>
    <span>· empty = not run · columns ordered by behavioural similarity</span>
  </div>
  <details class="model-filter" open>
    <summary>Show / hide model lanes <span id="model-filter-count"></span></summary>
    <div class="model-filter-actions">
      <button type="button" id="model-filter-all">All</button>
      <button type="button" id="model-filter-none">None</button>
      <button type="button" id="model-filter-invert">Invert</button>
    </div>
    <div class="model-filter-grid">{''.join(filter_items)}</div>
  </details>

  <h2 id="syndromes">Syndrome fingerprint</h2>
  <div class="panel">
    <table>
      <thead><tr><th class="corner">Syndrome</th>{th_models()}</tr></thead>
      <tbody>{''.join(body_syn)}</tbody>
    </table>
  </div>

  <h2 id="metrics">Metric fingerprint (grouped)</h2>
  <div class="panel">
    <table>
      <thead><tr><th class="corner">Metric</th>{th_models()}</tr></thead>
      <tbody>{''.join(body_metric)}</tbody>
    </table>
  </div>

  <footer>DSM-AE experimental UI · theme <code>{html.escape(t['id'])}</code> ·
    semantic layout from <code>scripts/experimental_metric_layout.py</code></footer>
  <div id="cell-tip" role="tooltip" hidden></div>
  <script>
  (function () {{
    // tooltips
    const tip = document.getElementById("cell-tip");
    document.addEventListener("pointerover", (ev) => {{
      const el = ev.target.closest("td[data-tip]");
      if (!el || !tip) return;
      tip.textContent = el.getAttribute("data-tip") || "";
      tip.hidden = false;
      tip.classList.add("visible");
      const x = Math.min(ev.clientX + 12, window.innerWidth - 200);
      const y = Math.min(ev.clientY + 14, window.innerHeight - 60);
      tip.style.left = x + "px";
      tip.style.top = y + "px";
    }});
    document.addEventListener("pointerout", (ev) => {{
      if (ev.target.closest && ev.target.closest("td[data-tip]")) {{
        tip.classList.remove("visible");
        tip.hidden = true;
      }}
    }});

    // column filter
    const boxes = Array.from(document.querySelectorAll("input.model-col-toggle"));
    const countEl = document.getElementById("model-filter-count");
    function apply() {{
      boxes.forEach((cb) => {{
        const col = cb.getAttribute("data-model-col");
        const on = cb.checked;
        document.querySelectorAll(
          "th.model[data-model-col='" + col + "'], td[data-model-col='" + col + "']"
        ).forEach((el) => el.classList.toggle("col-hidden", !on));
      }});
      if (countEl) {{
        const n = boxes.filter((b) => b.checked).length;
        countEl.textContent = "(" + n + "/" + boxes.length + " visible)";
      }}
    }}
    boxes.forEach((b) => b.addEventListener("change", apply));
    document.getElementById("model-filter-all")?.addEventListener("click", () => {{
      boxes.forEach((b) => b.checked = true); apply();
    }});
    document.getElementById("model-filter-none")?.addEventListener("click", () => {{
      boxes.forEach((b) => b.checked = false); apply();
    }});
    document.getElementById("model-filter-invert")?.addEventListener("click", () => {{
      boxes.forEach((b) => b.checked = !b.checked); apply();
    }});
    apply();
  }})();
  </script>
</body>
</html>
"""


def _short_model(m: str) -> str:
    # compact lane labels
    m = m.replace("qwen3.5-397b-a17b", "qwen3.5-397b")
    m = m.replace("deepseek-v4-flash-0731", "ds-flash-0731")
    m = m.replace("deepseek-v4-pro", "ds-pro")
    return m


def _nav_links(active: str) -> str:
    bits = []
    for t in THEMES:
        cls = "active" if t["id"] == active else ""
        bits.append(
            f'<a class="{cls}" href="{html.escape(t["id"])}.html">{html.escape(t["name"])}</a>'
        )
    return "\n".join(bits)


def _legend_bar(theme: Theme) -> str:
    fn = theme["cell_fn"]
    if fn == "ethidium":
        return "background:linear-gradient(90deg,#0a0a0a,#4a1020,#c43020,#ff8040,#ffc0a0)"
    if fn == "coomassie":
        return "background:linear-gradient(90deg,#f5f0e8,#a0b0d0,#2a4a9b,#102060)"
    if fn == "silver":
        return "background:linear-gradient(90deg,#f0ece6,#a8a49e,#404040,#101010)"
    if fn == "viridis":
        return "background:linear-gradient(90deg,#440154,#31688e,#35b779,#fde725)"
    if fn == "family":
        return "background:linear-gradient(90deg,#1a2030,#2a5080,#5080c0,#a0c0ff)"
    return "background:#444"


def build_index(generated: str) -> str:
    cards = []
    for t in THEMES:
        cards.append(
            f"""
    <a class="card" href="{html.escape(t['id'])}.html">
      <div class="swatch" style="{_legend_bar(t)};height:48px;border-radius:4px;margin-bottom:8px"></div>
      <strong>{html.escape(t['name'])}</strong>
      <p>{html.escape(t['blurb'])}</p>
    </a>"""
        )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>DSM-AE experimental UI gallery</title>
<style>
  body {{
    margin: 0; padding: 24px; font: 15px/1.45 system-ui, sans-serif;
    background: #0c0c10; color: #ece8e1;
  }}
  h1 {{ margin: 0 0 8px; font-size: 1.5rem; }}
  .meta {{ color: #999; font-size: 13px; margin-bottom: 20px; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px; max-width: 1100px;
  }}
  a.card {{
    display: block; padding: 14px; border: 1px solid #333; border-radius: 8px;
    background: #16161c; color: inherit; text-decoration: none;
  }}
  a.card:hover {{ border-color: #888; }}
  a.card p {{ margin: 6px 0 0; font-size: 13px; color: #aaa; }}
  .note {{ max-width: 48rem; margin: 24px 0; font-size: 13px; color: #bbb; }}
</style>
</head>
<body>
  <h1>DSM-AE experimental Comparison UIs</h1>
  <p class="meta">Generated {html.escape(generated)} · pick a gel variant ·
    metrics grouped by behavioural family · models ordered by fingerprint similarity</p>
  <div class="grid">{''.join(cards)}</div>
  <p class="note">
    These are design explorations on branch <code>experimental-ui</code>.
    Production Comparison remains <code>reports/dsm-ae-matrix.html</code>.
    Groups: agency → tools → planning → metacog → memory/recency → social → security → coding → multi-agent.
  </p>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--reports", type=Path, default=Path("reports"), help="Reports root"
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("reports/experimental-ui"),
        help="Output directory",
    )
    ap.add_argument("--include-mock", action="store_true")
    args = ap.parse_args(argv)

    paths = discover_jsons([args.reports])
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
        print("No reports found", file=sys.stderr)
        return 1

    by_model = merge_reports(reports)
    models, metrics, findings, packs = collect_universe_fixed(by_model)
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(build_index(generated), encoding="utf-8")
    for theme in THEMES:
        html_doc = build_variant_html(
            theme,
            by_model=by_model,
            models=list(models),
            metrics=list(metrics),
            finding_codes=list(findings),
            generated=generated,
        )
        path = out / f"{theme['id']}.html"
        path.write_text(html_doc, encoding="utf-8")
        print(f"Wrote {path}")
    print(f"Gallery → {out / 'index.html'} ({len(models)} models, {len(metrics)} metrics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
