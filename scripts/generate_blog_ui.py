#!/usr/bin/env python3
"""Pre-render docs/blog_post.md → reports/blog/index.html.

Matches the existing reports UI convention: a build script writes a static
``reports/<section>/index.html`` (see ``generate_literature_ui.py``,
``generate_compaction_ui.py``). No CDN markdown renderer — the only CDN dep in
this UI is mermaid, and markdown is already pre-rendered in Python elsewhere
(``json_to_html_report.md_to_appendix_html``,
``dsm_ae.queue.web_html.render_simple_markdown``).

All links out of the page are relative, so the page works both at
``/reports/blog/`` and under a ``/dsm-ae/`` path prefix.

Usage:
  python3 scripts/generate_blog_ui.py
  python3 scripts/generate_blog_ui.py --src docs/blog_post.md --out reports/blog/index.html
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "docs" / "blog_post.md"
DEFAULT_OUT = ROOT / "reports" / "blog" / "index.html"


# --------------------------------------------------------------------------
# markdown → html (same subset the appendix renderer supports, plus ordered
# lists, blockquotes, links, italics and horizontal rules)
# --------------------------------------------------------------------------


def _inline(text: str) -> str:
    """Escape, then apply inline markdown: code, bold, italic, links."""
    s = html.escape(text)
    # code spans first so their contents are not re-processed
    holes: list[str] = []

    def _stash(m: re.Match[str]) -> str:
        holes.append(f"<code>{m.group(1)}</code>")
        return f"\x00{len(holes) - 1}\x00"

    s = re.sub(r"`([^`]+)`", _stash, s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?!\w)", r"<em>\1</em>", s)
    s = re.sub(r"\x00(\d+)\x00", lambda m: holes[int(m.group(1))], s)
    return s


def _slug(text: str) -> str:
    s = re.sub(r"`|\*\*|\*", "", text).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "section"


def _table(rows: list[str]) -> str:
    parsed: list[list[str]] = []
    aligns: list[str] = []
    for row in rows:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{2,}:?", c.replace(" ", "")) for c in cells):
            for c in cells:
                c = c.replace(" ", "")
                if c.endswith(":") and c.startswith(":"):
                    aligns.append("center")
                elif c.endswith(":"):
                    aligns.append("right")
                else:
                    aligns.append("left")
            continue
        parsed.append(cells)
    if not parsed:
        return ""
    head, *body = parsed

    def _al(i: int) -> str:
        a = aligns[i] if i < len(aligns) else "left"
        return "" if a == "left" else f' style="text-align:{a}"'

    thead = (
        "<thead><tr>"
        + "".join(f"<th{_al(i)}>{_inline(c)}</th>" for i, c in enumerate(head))
        + "</tr></thead>"
    )
    parts = []
    for r in body:
        if len(r) < len(head):
            r = r + [""] * (len(head) - len(r))
        r = r[: len(head)]
        parts.append(
            "<tr>"
            + "".join(f"<td{_al(i)}>{_inline(c)}</td>" for i, c in enumerate(r))
            + "</tr>"
        )
    return (
        '<div class="panel"><table>'
        + thead
        + "<tbody>"
        + "".join(parts)
        + "</tbody></table></div>"
    )


def md_to_html(md: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Render markdown. Returns (html, [(level, slug, title), ...]) for the TOC."""
    lines = md.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    toc: list[tuple[int, str, str]] = []
    seen: dict[str, int] = {}
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]

        # fenced code
        if line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            code: list[str] = []
            while i < n and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if i < n:
                i += 1
            cls = f' class="lang-{html.escape(lang)}"' if lang else ""
            out.append(f"<pre{cls}><code>{html.escape(chr(10).join(code))}</code></pre>")
            continue

        # horizontal rule
        if re.fullmatch(r"\s*-{3,}\s*", line):
            out.append("<hr/>")
            i += 1
            continue

        # table
        if line.strip().startswith("|"):
            rows: list[str] = []
            while i < n and lines[i].strip().startswith("|"):
                rows.append(lines[i])
                i += 1
            out.append(_table(rows))
            continue

        if not line.strip():
            i += 1
            continue

        # heading
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            base = _slug(title)
            seen[base] = seen.get(base, 0) + 1
            slug = base if seen[base] == 1 else f"{base}-{seen[base]}"
            if level in (1, 2):
                toc.append((level, slug, re.sub(r"`|\*\*", "", title)))
            out.append(f'<h{level} id="{slug}">{_inline(title)}</h{level}>')
            i += 1
            continue

        # blockquote
        if line.lstrip().startswith(">"):
            quoted: list[str] = []
            while i < n and lines[i].lstrip().startswith(">"):
                quoted.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            inner, _ = md_to_html("\n".join(quoted))
            out.append(f"<blockquote>{inner}</blockquote>")
            continue

        # lists (ordered / unordered, one level of continuation lines)
        if re.match(r"^\s*(?:[-*]|\d+\.)\s+", line):
            ordered = bool(re.match(r"^\s*\d+\.\s+", line))
            items: list[str] = []
            while i < n and re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[i]):
                items.append(re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", lines[i]))
                i += 1
                # soft-wrapped continuation lines belong to the current item
                while (
                    i < n
                    and lines[i].strip()
                    and lines[i].startswith((" ", "\t"))
                    and not re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[i])
                ):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            tag = "ol" if ordered else "ul"
            out.append(
                f"<{tag}>" + "".join(f"<li>{_inline(it)}</li>" for it in items) + f"</{tag}>"
            )
            continue

        # paragraph (merge soft-wrapped lines)
        para = [line.strip()]
        i += 1
        while i < n:
            nxt = lines[i]
            if (
                not nxt.strip()
                or nxt.startswith("```")
                or nxt.strip().startswith("|")
                or nxt.lstrip().startswith(">")
                or re.match(r"^#{1,4}\s+", nxt)
                or re.match(r"^\s*(?:[-*]|\d+\.)\s+", nxt)
                or re.fullmatch(r"\s*-{3,}\s*", nxt)
            ):
                break
            para.append(nxt.strip())
            i += 1
        text = " ".join(para)
        # a paragraph that is only bold key/value lines reads better as meta
        cls = ' class="meta"' if text.startswith("**Status:**") else ""
        out.append(f"<p{cls}>{_inline(text)}</p>")
    return "\n".join(out), toc


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------

# Colour tokens, font stack and spacing rhythm are lifted from
# reports/dsm-ae-matrix.html (scripts/json_to_html_report.py) so the blog reads
# as the same document family. No new design language.
CSS = """
  body {
    margin: 0; padding: 10px 14px;
    font: 13px/1.35 system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    background: #fff; color: #111;
  }
  html.embedded-in-shell body { padding: 0 14px 8px; }
  .wrap { max-width: 860px; }
  h1 { margin: 0 0 4px; font-size: 1.2rem; }
  h2 { margin: 20px 0 6px; font-size: 1.05rem; }
  h3 { margin: 14px 0 6px; font-size: 0.95rem; }
  h4 { margin: 12px 0 4px; font-size: 0.9rem; }
  p { margin: 0 0 8px; line-height: 1.5; }
  .meta { margin: 0 0 6px; color: #444; font-size: 12px; }
  .toc { display: flex; flex-wrap: wrap; gap: 4px 12px; margin: 8px 0 12px; }
  .toc a { font-size: 12px; }
  nav.site { margin: 0 0 10px; font-size: 12px; }
  nav.site a { margin-right: 12px; }
  hr { border: 0; border-top: 1px solid #eee; margin: 18px 0; }
  ul, ol { margin: 0 0 8px; padding-left: 20px; }
  li { margin: 2px 0; line-height: 1.45; }
  blockquote {
    margin: 8px 0; padding: 2px 0 2px 12px;
    border-left: 3px solid #ccc; color: #444;
  }
  blockquote p { margin: 0 0 4px; }
  .panel {
    border: 1px solid #ccc; margin: 8px 0 12px;
    overflow-x: auto;
  }
  table {
    border-collapse: separate; border-spacing: 0;
    width: max-content; min-width: 100%; font-size: 12px;
  }
  th, td {
    border: 1px solid #ccc; padding: 3px 6px;
    text-align: left; vertical-align: top; background-clip: padding-box;
  }
  th { background: #f5f5f5; font-weight: 600; }
  td { font-variant-numeric: tabular-nums; }
  code { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }
  pre {
    background: #fafafa; border: 1px solid #ccc; padding: 8px 10px;
    overflow-x: auto; font-size: 12px; line-height: 1.4; margin: 8px 0 12px;
  }
  pre code { font-size: 12px; }
  a { color: #0645ad; }
  a:hover { text-decoration: underline; }
"""


def build_page(md: str, src_rel: str) -> str:
    body, toc = md_to_html(md)
    title = "Which Behaviours Actually Break the Job?"
    m = re.match(r"^#\s+(.*)$", md.lstrip().split("\n", 1)[0])
    if m:
        title = re.sub(r"`|\*\*", "", m.group(1)).strip()
    toc_html = "".join(
        f'<a href="#{s}">{html.escape(t)}</a>' for lvl, s, t in toc if lvl == 2
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>DSM-AE · {html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <nav class="site">
    <a href="../dsm-ae-matrix.html">Comparison matrix</a>
    <a href="../">Reports index</a>
  </nav>
  <p class="meta">Source: <code>{html.escape(src_rel)}</code> ·
    rebuild with <code>python3 scripts/generate_blog_ui.py</code></p>
  <div class="toc meta">{toc_html}</div>
{body}
</div>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    src: Path = args.src if args.src.is_absolute() else ROOT / args.src
    out: Path = args.out if args.out.is_absolute() else ROOT / args.out
    if not src.is_file():
        print(f"missing markdown source: {src}")
        return 1
    try:
        src_rel = str(src.relative_to(ROOT))
    except ValueError:
        src_rel = str(src)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(src.read_text(encoding="utf-8"), src_rel), encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
