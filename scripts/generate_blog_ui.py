#!/usr/bin/env python3
"""Pre-render docs/blog_post.md → reports/blog/index.html *and* a Hugo site.

Matches the existing reports UI convention: a build script writes a static
``reports/<section>/index.html`` (see ``generate_literature_ui.py``,
``generate_compaction_ui.py``). Markdown is pre-rendered in Python. The only
CDN dependency is mermaid.

Also writes ``reports/blog/site/`` and, if ``hugo`` is on PATH, builds
``reports/blog/hugo/``. Pipeline-shaped `` ```text `` fences become mermaid
flowcharts; remaining fences get a language tag. Sessions named in §1.5 and
Appendix A are exported (best-effort, Mongo) as JSONL and embedded in an
in-page viewer.

All links out of the page are relative, so the page works both at
``/reports/blog/`` and under a ``/dsm-ae/`` path prefix.

Usage:
  python3 scripts/generate_blog_ui.py
  python3 scripts/generate_blog_ui.py --src docs/blog_post.md --out reports/blog/index.html
  python3 scripts/generate_blog_ui.py --skip-hugo --skip-trajectories
  node scripts/serve_hugo_blog.js          # http://127.0.0.1:8766/
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SRC = ROOT / "docs" / "blog_post.md"
DEFAULT_OUT = ROOT / "reports" / "blog" / "index.html"
DEFAULT_HUGO_SRC = ROOT / "reports" / "blog" / "site"
DEFAULT_HUGO_DEST = ROOT / "reports" / "blog" / "hugo"
DEFAULT_TRAJ_DIR = ROOT / "reports" / "blog" / "trajectories"

# Sessions the body discusses in §1.5 (short prefixes; Mongo prefix-matches).
FEATURED_SESSIONS = (
    ("f4ac2beb", "185 permission refusals"),
    ("0614e0de", "tmux → 83 edits / 9 files"),
    ("b52e0124", "51-hour sleep 60 loop"),
    ("40b0660e", "62 consecutive Edit refusals"),
)

_FENCE_RE = re.compile(r"```([^\n]*)\n(.*?)```", re.S)
_ARROW_LINE = re.compile(r"^[↓→]\s*(.*)$")
_ATOM_LOG_LINE = re.compile(r"^\s*\d+\s+\w+")
_SESSION_ID_RE = re.compile(
    r"`([0-9a-f]{8}(?:-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})?)`",
    re.I,
)
_ROLE_SPLIT = re.compile(r"\n(user|assistant): ")


# --------------------------------------------------------------------------
# markdown preprocess: mermaid pipelines + consistent fence languages
# --------------------------------------------------------------------------


def infer_fence_lang(info: str, body: str) -> str:
    """Give every fence a language tag so highlighting/CSS stay consistent."""
    info = (info or "").strip().lower()
    if info and info not in {"text", "txt", "plain"}:
        return info
    first = next((ln.strip() for ln in body.splitlines() if ln.strip()), "")
    if first.startswith(("python", "from ", "import ", "def ", "class ")):
        return "python"
    if first.startswith(("export ", "# ", "curl ", "hugo ")) or first.startswith("python3"):
        return "bash"
    if first.startswith(("assistant:", "user:", "system:")):
        return "text"
    return "text"


def text_pipeline_to_mermaid(code: str) -> str | None:
    """Turn a ↓-pipeline listing into a mermaid flowchart, or None if it is not one."""
    raw = [ln.rstrip() for ln in code.splitlines() if ln.strip()]
    if len(raw) < 2:
        return None
    if sum(bool(_ATOM_LOG_LINE.match(ln)) for ln in raw) >= 3:
        return None
    if not any("↓" in ln or "→" in ln or _ARROW_LINE.match(ln.strip()) for ln in raw):
        return None

    nodes: list[str] = []
    edges: list[str] = []
    pending = ""
    for ln in raw:
        s = ln.strip()
        am = _ARROW_LINE.match(s)
        if am or s.startswith("↓") or (s.startswith("→") and len(s) < 80):
            pending = re.sub(r"^[↓→]\s*", "", s).strip(" ()")
            continue
        title, _, note = s.partition("←")
        title = re.sub(r"\s+", " ", title).strip()
        if note.strip():
            title = f"{title}<br/><i>{html.escape(note.strip())}</i>"
        if not title:
            continue
        if nodes:
            edges.append(pending)
        pending = ""
        nodes.append(title)
    if len(nodes) < 2:
        return None

    def _nid(i: int) -> str:
        return f"n{i}"

    def _qlabel(s: str) -> str:
        # mermaid node text; keep <br/> from above
        return s.replace('"', "#quot;")

    lines = ["flowchart TD"]
    for i, label in enumerate(nodes):
        lines.append(f'  {_nid(i)}["{_qlabel(label)}"]')
    for i, elabel in enumerate(edges):
        if elabel:
            lines.append(f'  {_nid(i)} -->|"{html.escape(elabel)}"| {_nid(i + 1)}')
        else:
            lines.append(f"  {_nid(i)} --> {_nid(i + 1)}")
    return "\n".join(lines)


def preprocess_markdown(md: str) -> str:
    """Rewrite fences: pipelines → mermaid; everything else gets a language."""

    def _one(m: re.Match[str]) -> str:
        info, body = m.group(1), m.group(2)
        info_l = (info or "").strip().lower()
        if info_l in {"", "text", "txt", "plain"}:
            mermaid = text_pipeline_to_mermaid(body)
            if mermaid:
                return f"```mermaid\n{mermaid}\n```"
        lang = infer_fence_lang(info, body)
        return f"```{lang}\n{body.rstrip()}\n```"

    return _FENCE_RE.sub(_one, md)


# --------------------------------------------------------------------------
# trajectories → JSONL (best-effort; never blocks the blog build)
# --------------------------------------------------------------------------


def _redact(text: str) -> str:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import mine_sessions  # type: ignore

        return mine_sessions.redact(text)
    except Exception:
        return text


def _cut_system_prompt(text: str) -> str:
    last = text.rfind("</example>")
    if last >= 0:
        return text[last + len("</example>") :]
    i = text.find("\nuser:")
    return text[i:] if i >= 0 else text


def session_text_to_events(text: str, *, cap: int) -> list[dict]:
    """Split a redacted session_text into Docent-style turn/tool events."""
    chunk = _cut_system_prompt(text)
    bits = _ROLE_SPLIT.split("\n" + chunk)
    events: list[dict] = []
    # bits: [preamble, role, content, role, content, ...]
    i = 1
    while i + 1 < len(bits) and len(events) < cap:
        role, content = bits[i], bits[i + 1]
        i += 2
        # peel tool_use / tool_result out as their own cards
        pos = 0
        for m in re.finditer(
            r"\[tool_use (\w+)(?:: (.*?))?\]|\[tool_result:(.*?)(?=\n(?:user|assistant): |\n\[tool_use |\Z)",
            content,
            re.S,
        ):
            prose = content[pos : m.start()].strip()
            if prose and role == "assistant":
                events.append({"type": "message", "role": "assistant", "text": prose[:4000]})
            pos = m.end()
            if m.group(1):
                events.append({
                    "type": "tool_call",
                    "role": "assistant",
                    "tool": m.group(1),
                    "text": (m.group(2) or "")[:2000],
                })
            else:
                events.append({
                    "type": "tool_result",
                    "role": "user",
                    "tool": "result",
                    "text": (m.group(3) or "").strip()[:4000],
                })
            if len(events) >= cap:
                break
        rest = content[pos:].strip()
        if rest and len(events) < cap:
            if role == "user" and rest.startswith("[tool_result"):
                continue
            events.append({"type": "message", "role": role, "text": rest[:4000]})
    return events


def extract_session_ids(md: str) -> list[tuple[str, str, bool]]:
    """(prefix, label, featured) from §1.5 + Appendix A."""
    featured = {p: lab for p, lab in FEATURED_SESSIONS}
    found: dict[str, tuple[str, bool]] = {}
    for m in _SESSION_ID_RE.finditer(md):
        raw = m.group(1)
        prefix = raw[:8].lower()
        if prefix in featured:
            found[prefix] = (featured[prefix], True)
        else:
            found.setdefault(prefix, (raw, False))
    # featured first, then appendix
    out = [(p, lab, True) for p, lab in FEATURED_SESSIONS if p in found]
    for p, (lab, feat) in found.items():
        if not feat:
            out.append((p, lab, False))
    return out


def export_trajectories(md: str, dest: Path) -> dict:
    """Write JSONL + index.json. Returns the index payload (possibly empty)."""
    dest.mkdir(parents=True, exist_ok=True)
    wanted = extract_session_ids(md)
    index: dict = {"sessions": [], "source": "session_labels_by_gpt55", "ok": False}
    try:
        import pymongo
    except ImportError:
        (dest / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index

    uri = os.environ.get("DSM_MONGO_URI", "mongodb://localhost:27018/")
    try:
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=2000)
        client.admin.command("ping")
        coll = client["claude_conversations"]["session_labels_by_gpt55"]
    except Exception as exc:
        index["error"] = f"{type(exc).__name__}: {exc}"
        (dest / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
        return index

    for prefix, label, featured in wanted:
        cap = 500 if featured else 80
        doc = coll.find_one(
            {"session_id": {"$regex": f"^{re.escape(prefix)}"}},
            {"auth_token": 0},
        )
        if not doc:
            continue
        text = _redact(doc.get("session_text") or "")
        events = session_text_to_events(text, cap=cap)
        fname = f"{prefix}.jsonl"
        path = dest / fname
        with path.open("w", encoding="utf-8") as fh:
            for ev in events:
                fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
        index["sessions"].append({
            "id": doc.get("session_id"),
            "short": prefix,
            "label": label,
            "featured": featured,
            "n_events": len(events),
            "request_count": doc.get("request_count"),
            "category": doc.get("session_task_category"),
            "model": doc.get("model"),
            "file": fname,
            "truncated": len(events) >= cap,
        })
    index["ok"] = True
    (dest / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


def _viewer_html(index: dict, jsonl_href: str) -> str:
    n = len(index.get("sessions") or [])
    status = (
        f"{n} session{'s' if n != 1 else ''} exported"
        if index.get("ok")
        else "trajectories not exported (Mongo unavailable at build time)"
    )
    return (
        f'<div class="traj-viewer" data-index="{html.escape(jsonl_href)}">'
        f'<div class="traj-status meta">{html.escape(status)}. '
        f"Click a session, then a turn. Payloads are redacted on export.</div>"
        f'<div class="traj-layout">'
        f'<aside class="traj-list"></aside>'
        f'<section class="traj-main">'
        f'<div class="traj-toolbar">'
        f'<input type="search" class="traj-search" placeholder="filter turns…"/>'
        f'<select class="traj-filter">'
        f'<option value="">all types</option>'
        f'<option value="message">messages</option>'
        f'<option value="tool_call">tool calls</option>'
        f'<option value="tool_result">tool results</option>'
        f"</select></div>"
        f'<div class="traj-events"></div>'
        f"</section></div></div>"
    )


def inject_viewers(md: str, index: dict) -> str:
    """Drop a viewer under §1.5 and Appendix A."""
    viewer_15 = "\n\n" + _viewer_html(index, "trajectories/index.json") + "\n\n"
    viewer_app = "\n\n" + _viewer_html(index, "trajectories/index.json") + "\n\n"
    md = re.sub(
        r"(^### 1\.5[^\n]*\n)",
        r"\1" + viewer_15,
        md,
        count=1,
        flags=re.M,
    )
    md = re.sub(
        r"(^## Appendix A[^\n]*\n)",
        r"\1" + viewer_app,
        md,
        count=1,
        flags=re.M,
    )
    return md


# --------------------------------------------------------------------------
# markdown → html (same subset the appendix renderer supports, plus ordered
# lists, blockquotes, links, italics and horizontal rules)
# --------------------------------------------------------------------------


# Block-level tags passed through verbatim rather than escaped. Deliberately
# narrow: containers only, so the source stays trusted-authored markdown and no
# script/style/event-handler surface is introduced.
_RAW_HTML_BLOCK_TAGS = frozenset({"details", "summary", "div", "figure", "figcaption"})


def _is_raw_html_block_line(line: str) -> bool:
    """True for a line that is exactly one allowlisted block tag, open or close."""
    m = re.match(r"^\s*(</?)(\w+)([^>]*)>\s*$", line)
    return bool(m) and m.group(2).lower() in _RAW_HTML_BLOCK_TAGS


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

        # raw block-level HTML passthrough (e.g. <details>/<summary> wrappers).
        # Emitted verbatim; the markdown between the open and close tags is
        # still rendered, which is what GFM does for blank-line-separated
        # content inside a block element.
        if _is_raw_html_block_line(line) or line.strip().startswith('<div class="traj-viewer"'):
            out.append(line.strip())
            i += 1
            continue

        # a one-line <summary>…</summary> keeps its inline markdown
        m_sum = re.match(r"^\s*<summary>(.*)</summary>\s*$", line, re.I)
        if m_sum:
            out.append(f"<summary>{_inline(m_sum.group(1).strip())}</summary>")
            i += 1
            continue

        # fenced code / mermaid
        if line.startswith("```"):
            info = line[3:].strip()
            i += 1
            code: list[str] = []
            while i < n and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if i < n:
                i += 1
            body = chr(10).join(code)
            lang = infer_fence_lang(info, body)
            if lang == "mermaid":
                # trusted generated source; escaping would break mermaid quotes
                safe = body.replace("</", "<\\/")
                out.append(f'<div class="mermaid">{safe}</div>')
            else:
                out.append(
                    f'<pre class="lang-{html.escape(lang)}" data-lang="{html.escape(lang)}">'
                    f"<code>{html.escape(body)}</code></pre>"
                )
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
                # soft-wrapped continuation lines belong to the current item; a
                # blank line followed by more indented prose continues the same
                # item as a new paragraph rather than ending the list.
                while i < n:
                    if (
                        lines[i].strip()
                        and lines[i].startswith((" ", "\t"))
                        and not re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[i])
                    ):
                        items[-1] += " " + lines[i].strip()
                        i += 1
                        continue
                    nxt = i + 1
                    if (
                        not lines[i].strip()
                        and nxt < n
                        and lines[nxt].strip()
                        and lines[nxt].startswith((" ", "\t"))
                        and not re.match(r"^\s*(?:[-*]|\d+\.)\s+", lines[nxt])
                    ):
                        items[-1] += "\x01" + lines[nxt].strip()
                        i = nxt + 1
                        continue
                    break
            tag = "ol" if ordered else "ul"

            def _li(item: str) -> str:
                paras = item.split("\x01")
                if len(paras) == 1:
                    return f"<li>{_inline(paras[0])}</li>"
                body = "".join(f"<p>{_inline(p)}</p>" for p in paras)
                return f"<li>{body}</li>"

            out.append(
                f"<{tag}>" + "".join(_li(it) for it in items) + f"</{tag}>"
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
                or _is_raw_html_block_line(nxt)
                or nxt.strip().startswith('<div class="traj-viewer"')
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
    background: #f6f8fa; border: 1px solid #d0d7de; padding: 18px 10px 8px;
    overflow-x: auto; font-size: 12px; line-height: 1.45; margin: 8px 0 12px;
    position: relative; border-radius: 4px;
  }
  pre code { font-size: 12px; }
  pre[data-lang]::before {
    content: attr(data-lang);
    position: absolute; top: 2px; right: 8px;
    font: 10px/1.4 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    color: #666; text-transform: lowercase;
  }
  .mermaid { margin: 10px 0 14px; overflow-x: auto; }
  .traj-viewer { border: 1px solid #ccc; margin: 10px 0 16px; background: #fff; }
  .traj-status { padding: 6px 10px; border-bottom: 1px solid #eee; }
  .traj-layout { display: flex; min-height: 280px; max-height: 520px; }
  .traj-list {
    width: 220px; overflow-y: auto; border-right: 1px solid #eee;
    font-size: 12px; flex-shrink: 0;
  }
  .traj-list button {
    display: block; width: 100%; text-align: left; border: 0;
    background: transparent; padding: 6px 8px; cursor: pointer;
    border-bottom: 1px solid #f0f0f0; font: inherit;
  }
  .traj-list button:hover, .traj-list button.active { background: #f0f4ff; }
  .traj-list .sid { font-family: ui-monospace, Menlo, Consolas, monospace; color: #444; }
  .traj-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
  .traj-toolbar { display: flex; gap: 6px; padding: 6px 8px; border-bottom: 1px solid #eee; }
  .traj-toolbar input, .traj-toolbar select { font: 12px system-ui; }
  .traj-toolbar input { flex: 1; }
  .traj-events { overflow-y: auto; padding: 6px 8px; font-size: 12px; }
  .traj-ev {
    border: 1px solid #e5e5e5; margin: 0 0 6px; padding: 4px 8px;
    background: #fafafa; cursor: pointer;
  }
  .traj-ev .who { font-weight: 600; margin-right: 6px; }
  .traj-ev.tool_call { border-left: 3px solid #4a7; }
  .traj-ev.tool_result { border-left: 3px solid #888; }
  .traj-ev.message.assistant { border-left: 3px solid #36c; }
  .traj-ev.message.user { border-left: 3px solid #c63; }
  .traj-ev pre { margin: 4px 0 0; max-height: 240px; display: none; }
  .traj-ev.open pre { display: block; }
  a { color: #0645ad; }
  a:hover { text-decoration: underline; }
  details {
    border: 1px solid #ccc; background: #fafafa;
    padding: 6px 10px; margin: 8px 0 12px;
  }
  details[open] { background: #fff; }
  details > summary {
    cursor: pointer; font-weight: 600; font-size: 12px;
    margin: 0 -10px; padding: 0 10px;
  }
  details[open] > summary { margin-bottom: 6px; }
  details > summary:hover { color: #0645ad; }
  details > :last-child { margin-bottom: 0; }
"""

TRAJ_JS = r"""
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  async function loadIndex(url) {
    const r = await fetch(url);
    if (!r.ok) throw new Error(url + " " + r.status);
    return r.json();
  }

  async function loadEvents(base, file) {
    const r = await fetch(base + file);
    if (!r.ok) throw new Error(file + " " + r.status);
    const text = await r.text();
    return text.split("\n").filter(Boolean).map(function (ln) { return JSON.parse(ln); });
  }

  function renderList(box, sessions, onPick) {
    box.innerHTML = "";
    sessions.forEach(function (s) {
      const b = document.createElement("button");
      b.type = "button";
      const tag = s.featured ? " · featured" : "";
      b.innerHTML = '<span class="sid">' + s.short + "</span>" + tag +
        "<br/>" + (s.label || "") +
        (s.n_events != null ? " · " + s.n_events + " turns" : "");
      b.addEventListener("click", function () {
        $all("button", box).forEach(function (x) { x.classList.remove("active"); });
        b.classList.add("active");
        onPick(s);
      });
      box.appendChild(b);
    });
  }

  function renderEvents(box, events, q, typ) {
    box.innerHTML = "";
    const needle = (q || "").toLowerCase();
    events.forEach(function (ev, i) {
      if (typ && ev.type !== typ) return;
      const blob = ((ev.text || "") + " " + (ev.tool || "")).toLowerCase();
      if (needle && blob.indexOf(needle) < 0) return;
      const d = document.createElement("div");
      d.className = "traj-ev " + (ev.type || "") + " " + (ev.role || "");
      const who = ev.tool ? (ev.type + " · " + ev.tool) : (ev.role || ev.type);
      const preview = (ev.text || "").replace(/\s+/g, " ").slice(0, 160);
      d.innerHTML = '<span class="who">' + who + "</span>" +
        '<span class="preview">' + preview + "</span>" +
        "<pre><code></code></pre>";
      d.querySelector("code").textContent = ev.text || "";
      d.addEventListener("click", function () { d.classList.toggle("open"); });
      box.appendChild(d);
    });
    if (!box.children.length) box.textContent = "no matching turns";
  }

  async function mount(el) {
    const idxUrl = el.getAttribute("data-index");
    const base = idxUrl.replace(/index\.json$/, "");
    let idx;
    try { idx = await loadIndex(idxUrl); }
    catch (e) {
      $(".traj-status", el).textContent = "could not load " + idxUrl;
      return;
    }
    const sessions = idx.sessions || [];
    if (!sessions.length) {
      $(".traj-status", el).textContent = idx.error || "no sessions exported";
      return;
    }
    let current = [];
    const list = $(".traj-list", el);
    const eventsBox = $(".traj-events", el);
    const search = $(".traj-search", el);
    const filter = $(".traj-filter", el);
    function redraw() { renderEvents(eventsBox, current, search.value, filter.value); }
    search.addEventListener("input", redraw);
    filter.addEventListener("change", redraw);
    renderList(list, sessions, async function (s) {
      eventsBox.textContent = "loading…";
      try { current = await loadEvents(base, s.file); }
      catch (e) { eventsBox.textContent = String(e); return; }
      redraw();
    });
    list.querySelector("button") && list.querySelector("button").click();
  }

  $all(".traj-viewer").forEach(mount);
})();
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
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "strict" }});
</script>
<script>{TRAJ_JS}</script>
</body>
</html>
"""


HUGO_TOML = """
baseURL = "/"
languageCode = "en-gb"
title = "DSM-AE"
disableKinds = ["taxonomy", "term", "RSS", "sitemap"]
[markup.goldmark.renderer]
  unsafe = true
[markup.goldmark.extensions.passthrough]
  enable = false
[markup.highlight]
  noClasses = false
  style = "github"
"""

HUGO_BASEOF = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{{ .Title }}</title>
<link rel="stylesheet" href="{{ "css/blog.css" | relURL }}"/>
</head>
<body>
<div class="wrap">
{{ block "main" . }}{{ end }}
</div>
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  mermaid.initialize({ startOnLoad: true, theme: "neutral", securityLevel: "strict" });
</script>
<script src="{{ "js/traj-viewer.js" | relURL }}"></script>
</body>
</html>
"""

HUGO_INDEX = """{{ define "main" }}
<nav class="site">
  <a href="../dsm-ae-matrix.html">Comparison matrix</a>
  <a href="../">Reports index</a>
</nav>
{{ .Content }}
{{ end }}
"""

HUGO_MERMAID_HOOK = """<div class="mermaid">
{{ .Inner | safeHTML }}
</div>
"""


def write_hugo_site(md: str, site: Path, traj_dir: Path) -> None:
    """Author a minimal Hugo project from the preprocessed markdown."""
    if site.exists():
        shutil.rmtree(site)
    (site / "content").mkdir(parents=True)
    (site / "layouts" / "_default").mkdir(parents=True)
    (site / "layouts" / "_default" / "_markup").mkdir(parents=True)
    (site / "static" / "css").mkdir(parents=True)
    (site / "static" / "js").mkdir(parents=True)
    (site / "hugo.toml").write_text(HUGO_TOML.strip() + "\n", encoding="utf-8")
    (site / "layouts" / "_default" / "baseof.html").write_text(HUGO_BASEOF, encoding="utf-8")
    (site / "layouts" / "index.html").write_text(HUGO_INDEX, encoding="utf-8")
    (site / "layouts" / "_default" / "_markup" / "render-codeblock-mermaid.html").write_text(
        HUGO_MERMAID_HOOK, encoding="utf-8"
    )
    (site / "static" / "css" / "blog.css").write_text(CSS, encoding="utf-8")
    (site / "static" / "js" / "traj-viewer.js").write_text(TRAJ_JS, encoding="utf-8")
    fm = "---\ntitle: Diagnosing Agentic Behaviour in Benchmarks and Real World Use\n---\n\n"
    (site / "content" / "_index.md").write_text(fm + md, encoding="utf-8")
    static_traj = site / "static" / "trajectories"
    if traj_dir.is_dir():
        if static_traj.exists():
            shutil.rmtree(static_traj)
        shutil.copytree(traj_dir, static_traj)


def run_hugo(site: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["hugo", "--quiet", "-s", str(site), "-d", str(dest)],
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--hugo-src", type=Path, default=DEFAULT_HUGO_SRC)
    ap.add_argument("--hugo-dest", type=Path, default=DEFAULT_HUGO_DEST)
    ap.add_argument("--traj-dir", type=Path, default=DEFAULT_TRAJ_DIR)
    ap.add_argument("--skip-hugo", action="store_true")
    ap.add_argument("--skip-trajectories", action="store_true")
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

    raw = src.read_text(encoding="utf-8")
    md = preprocess_markdown(raw)

    traj_dir = args.traj_dir if args.traj_dir.is_absolute() else ROOT / args.traj_dir
    index: dict = {"sessions": [], "ok": False}
    if not args.skip_trajectories:
        index = export_trajectories(md, traj_dir)
        print(f"trajectories: {len(index.get('sessions') or [])} "
              f"({'ok' if index.get('ok') else index.get('error', 'skipped')})")
    md = inject_viewers(md, index)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_page(md, src_rel), encoding="utf-8")
    print(f"wrote {out}")

    # sibling copy so the static HTML can fetch trajectories/index.json
    sibling = out.parent / "trajectories"
    if traj_dir.is_dir() and sibling.resolve() != traj_dir.resolve():
        if sibling.exists():
            shutil.rmtree(sibling)
        shutil.copytree(traj_dir, sibling)

    if not args.skip_hugo:
        site = args.hugo_src if args.hugo_src.is_absolute() else ROOT / args.hugo_src
        dest = args.hugo_dest if args.hugo_dest.is_absolute() else ROOT / args.hugo_dest
        write_hugo_site(md, site, traj_dir)
        try:
            run_hugo(site, dest)
            print(f"hugo wrote {dest}")
        except FileNotFoundError:
            print("hugo not on PATH; wrote project at", site)
        except subprocess.CalledProcessError as exc:
            print(f"hugo failed ({exc.returncode}); project is at {site}")
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
