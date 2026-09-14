import MarkdownIt from "markdown-it";

const ARROW = /^[↓→]\s*(.*)$/;
const ATOM = /^\s*\d+\s+\w+/;

export function pipelineToMermaid(code: string): string | null {
  const raw = code.split("\n").map((l) => l.trimEnd()).filter((l) => l.trim());
  if (raw.length < 2) return null;
  if (raw.filter((l) => ATOM.test(l)).length >= 3) return null;
  if (!raw.some((l) => l.includes("↓") || l.includes("→") || ARROW.test(l.trim()))) {
    return null;
  }
  const nodes: string[] = [];
  const edges: string[] = [];
  let pending = "";
  for (const ln of raw) {
    const s = ln.trim();
    if (ARROW.test(s) || s.startsWith("↓")) {
      pending = s.replace(/^[↓→]\s*/, "").replace(/^[()]+|[()]+$/g, "").trim();
      continue;
    }
    const [titleRaw, ...note] = s.split("←");
    let title = titleRaw.replace(/\s+/g, " ").trim();
    if (note.length) title += `<br/><i>${note.join("←").trim()}</i>`;
    if (!title) continue;
    if (nodes.length) edges.push(pending);
    pending = "";
    nodes.push(title);
  }
  if (nodes.length < 2) return null;
  const lines = ["flowchart TD"];
  nodes.forEach((n, i) => lines.push(`  n${i}["${n.replace(/"/g, "#quot;")}"]`));
  edges.forEach((e, i) => {
    lines.push(e ? `  n${i} -->|"${e}"| n${i + 1}` : `  n${i} --> n${i + 1}`);
  });
  return lines.join("\n");
}

export function renderMarkdown(src: string): string {
  const md = new MarkdownIt({ html: true, linkify: true, breaks: false });
  const defaultFence = md.renderer.rules.fence!;
  md.renderer.rules.fence = (tokens, idx, options, env, slf) => {
    const token = tokens[idx];
    const info = (token.info || "").trim().toLowerCase();
    let body = token.content;
    if (info === "text" || info === "" || info === "txt") {
      const mermaid = pipelineToMermaid(body);
      if (mermaid) {
        return `<div class="mermaid">${mermaid}</div>\n`;
      }
    }
    if (info === "mermaid") {
      return `<div class="mermaid">${body}</div>\n`;
    }
    return defaultFence(tokens, idx, options, env, slf);
  };
  return md.render(src);
}
