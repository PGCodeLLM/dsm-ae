"""HTML page for the queue UI (kept separate from FastAPI routes)."""
from __future__ import annotations

import json

from dsm_ae.packs.registry import list_packs
from dsm_ae.queue.store import JobStore


def _esc(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_queue_page(store: JobStore, href, auth_required: bool, title: str) -> str:
    packs = list_packs()
    pack_checks = "\n".join(
        f'<label class="pack-item"><input type="checkbox" class="pack-cb" value="{_esc(p)}"/>'
        f"<span>{_esc(p)}</span></label>"
        for p in packs
    )
    sample = href("/queue")
    configured_base = ""
    if sample.startswith("/") and sample.endswith("/queue"):
        configured_base = sample[: -len("/queue")]
    token_row = ""
    if auth_required:
        token_row = """
        <label>Queue token
          <input type="password" name="token" id="token" placeholder="shared token for enqueue"
                 autocomplete="off" data-persist="token"/>
        </label>
        """
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{_esc(title)} · DSM-AE Eval Queue</title>
<style>
  :root {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; }}
  body {{ margin: 0; padding: 16px 18px; background: #fafafa; color: #111; }}
  h1 {{ font-size: 1.25rem; margin: 0 0 4px; }}
  h2 {{ font-size: 1.05rem; margin: 18px 0 8px; }}
  .meta {{ color: #555; font-size: 13px; margin: 0 0 12px; }}
  nav a {{ margin-right: 12px; color: #0645ad; }}
  .panel {{ background: #fff; border: 1px solid #ddd; border-radius: 6px;
            padding: 12px 14px; margin: 0 0 14px; }}
  table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
  th, td {{ border: 1px solid #e0e0e0; padding: 4px 6px; text-align: left; vertical-align: top; }}
  th {{ background: #f5f5f5; }}
  form.enqueue label {{ display: block; margin: 0 0 8px; font-size: 13px; }}
  form.enqueue input[type=text], form.enqueue input[type=number],
  form.enqueue input[type=password], form.enqueue input[type=url] {{
    width: min(480px, 100%); padding: 4px 6px; margin-top: 2px; box-sizing: border-box;
  }}
  form.enqueue button, button.action, .btn {{
    background: #1565c0; color: #fff; border: 0; border-radius: 4px;
    padding: 6px 12px; cursor: pointer; font-size: 13px;
  }}
  button.action {{ background: #555; padding: 2px 8px; font-size: 12px; }}
  button.action:disabled, .btn:disabled {{ opacity: 0.5; cursor: not-allowed; }}
  .btn-test {{ background: #00897b; margin-left: 6px; }}
  code {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; }}
  .hint {{ color: #666; font-size: 12px; }}
  .hint.ok {{ color: #2e7d32; }}
  .hint.err {{ color: #c62828; }}
  .status {{ color: #fff; padding: 1px 6px; border-radius: 3px; font-size: 12px; }}
  .st-queued {{ background: #0288d1; }}
  .st-running {{ background: #f9a825; color: #111; }}
  .st-succeeded {{ background: #2e7d32; }}
  .st-failed {{ background: #c62828; }}
  .st-cancelled {{ background: #757575; }}
  #flash {{ margin: 0 0 10px; font-size: 13px; min-height: 1.2em; }}
  #flash.ok {{ color: #2e7d32; }}
  #flash.err {{ color: #c62828; }}
  #conn-result {{ margin: 4px 0 8px; font-size: 13px; min-height: 1.2em; }}
  #conn-result.ok {{ color: #2e7d32; }}
  #conn-result.err {{ color: #c62828; }}
  .row-inline {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px 16px; max-width: 720px; }}
  @media (max-width: 700px) {{ .grid2 {{ grid-template-columns: 1fr; }} }}
  fieldset.conn {{ border: 1px solid #ddd; border-radius: 6px; padding: 10px 12px; margin: 0 0 10px; max-width: 720px; }}
  fieldset.conn legend {{ font-size: 13px; font-weight: 600; padding: 0 4px; }}
  .pack-dd {{ position: relative; max-width: 480px; }}
  .pack-toggle {{
    width: 100%; text-align: left; background: #fff; color: #111;
    border: 1px solid #ccc; border-radius: 4px; padding: 6px 8px; cursor: pointer;
  }}
  .pack-panel {{
    display: none; position: absolute; z-index: 20; left: 0; right: 0;
    max-height: 240px; overflow: auto; background: #fff; border: 1px solid #ccc;
    border-radius: 4px; margin-top: 2px; box-shadow: 0 4px 12px rgba(0,0,0,.08);
    padding: 6px;
  }}
  .pack-dd.open .pack-panel {{ display: block; }}
  .pack-item {{ display: flex; align-items: center; gap: 6px; margin: 0 0 4px; font-size: 13px; cursor: pointer; }}
  .pack-item input {{ width: auto; margin: 0; }}
  .pack-actions {{ display: flex; gap: 8px; margin: 0 0 6px; }}
  .pack-actions button {{ background: #eee; color: #333; padding: 2px 8px; font-size: 12px; }}
  .prog {{ font-size: 11px; color: #444; min-width: 120px; }}
  .prog-bar {{ height: 6px; background: #eee; border-radius: 3px; overflow: hidden; margin-top: 2px; max-width: 140px; }}
  .prog-bar > i {{ display: block; height: 100%; background: #1565c0; width: 0%; }}
</style>
</head>
<body data-configured-base="{_esc(configured_base)}">
  <h1>DSM-AE evaluation queue</h1>
  <p class="meta">Enqueue models · LiteLLM-style connection · pack multi-select · live progress files</p>
  <nav>
    <a href="{href("/")}" data-nav="/">Queue</a>
    <a href="{href("/matrix")}" data-nav="/matrix" target="_blank" rel="noopener">Comparison matrix</a>
    <a href="{href("/reports/")}" data-nav="/reports/" target="_blank" rel="noopener">Reports</a>
    <a href="{href("/docs")}" data-nav="/docs" target="_blank" rel="noopener">API docs</a>
  </nav>
  <div id="flash" role="status" aria-live="polite"></div>

  <div class="panel">
    <h2>Jobs <span id="jobs-updated" class="hint"></span></h2>
    <table>
      <thead>
        <tr>
          <th>ID</th><th>Status</th><th>Model</th><th>Progress</th><th>k</th><th>Packs</th>
          <th>Label</th><th>Created</th><th>Error</th><th></th>
        </tr>
      </thead>
      <tbody id="jobs-body">
        <tr><td colspan="10" style="color:#666">Loading…</td></tr>
      </tbody>
    </table>
    <p class="hint">Jobs + progress refresh every 5s without reloading the form.</p>
  </div>

  <div class="panel">
    <h2>Enqueue</h2>
    <form class="enqueue" id="enqueue-form" method="post" action="{href("/queue")}">
      {token_row}

      <fieldset class="conn">
        <legend>Model connection (LiteLLM-style)</legend>
        <div class="grid2">
          <label>Model id
            <input type="text" name="model" id="f-model" required
                   placeholder="gpt-5.6-terra or mock/well_attuned"
                   autocomplete="off" data-persist="model"/>
          </label>
          <label>API base URL
            <input type="url" name="api_base" id="f-api-base"
                   placeholder="https://host/v1"
                   autocomplete="off" data-persist="api_base"/>
          </label>
          <label>API key
            <input type="password" name="api_key" id="f-api-key"
                   placeholder="sk-… (optional if models.yaml / mock)"
                   autocomplete="off"/>
          </label>
          <label>Timeout (seconds)
            <input type="number" name="timeout" id="f-timeout" value="120" min="5" max="600"
                   data-persist="timeout"/>
          </label>
        </div>
        <p class="hint">Leave API base/key empty for <code>mock/*</code> or models already in models.yaml. Keys go to a local secrets file (mode 0600), never returned by the API.</p>
        <div class="row-inline">
          <button type="button" class="btn btn-test" id="test-conn-btn">Test connection</button>
          <span id="conn-result" role="status"></span>
        </div>
      </fieldset>

      <label>Packs
        <div class="pack-dd" id="pack-dd">
          <button type="button" class="pack-toggle" id="pack-toggle">Select packs…</button>
          <div class="pack-panel" id="pack-panel">
            <div class="pack-actions">
              <button type="button" id="pack-all">All</button>
              <button type="button" id="pack-none">None</button>
            </div>
            {pack_checks}
          </div>
        </div>
      </label>
      <label class="hint" style="display:flex;align-items:center;gap:6px">
        <input type="checkbox" id="f-full-cb" style="width:auto"/> Full suite (all registered packs)
      </label>

      <div class="grid2">
        <label>k (bootstrap trials)
          <input type="number" name="k" id="f-k" value="3" min="1" max="50" data-persist="k"/>
        </label>
        <label>Concurrency (pack×trial)
          <input type="number" name="concurrency" id="f-concurrency" value="1" min="1" max="32" data-persist="concurrency"/>
        </label>
        <label>Priority
          <input type="number" name="priority" id="f-priority" value="0" data-persist="priority"/>
        </label>
        <label>Label (optional)
          <input type="text" name="label" id="f-label" placeholder="demo-run" data-persist="label"/>
        </label>
      </div>
      <button type="submit" id="enqueue-btn">Enqueue</button>
    </form>
  </div>

<script>
(function () {{
  const AUTH_REQUIRED = {json.dumps(auth_required)};
  const STORAGE_KEY = "dsm-ae-queue-form-v2";
  const POLL_MS = 5000;

  function detectBase() {{
    const p = location.pathname || "/";
    if (p === "/dsm-ae" || p.startsWith("/dsm-ae/")) return "/dsm-ae";
    const configured = (document.body.dataset.configuredBase || "").replace(/\\/$/, "");
    if (configured && (p === configured || p.startsWith(configured + "/"))) return configured;
    return "";
  }}
  const BASE = detectBase();
  function href(path) {{
    if (!path.startsWith("/")) path = "/" + path;
    return BASE + path;
  }}
  const API_JOBS = href("/api/jobs");
  const API_TEST = href("/api/test-connection");

  document.querySelectorAll("a[data-nav]").forEach((a) => {{
    a.setAttribute("href", href(a.getAttribute("data-nav") || "/"));
  }});
  const formEl = document.getElementById("enqueue-form");
  if (formEl) formEl.setAttribute("action", href("/queue"));

  function flash(msg, ok) {{
    const el = document.getElementById("flash");
    el.textContent = msg || "";
    el.className = msg ? (ok ? "ok" : "err") : "";
  }}
  function connMsg(msg, ok) {{
    const el = document.getElementById("conn-result");
    el.textContent = msg || "";
    el.className = msg ? (ok ? "ok" : "err") : "";
  }}
  function authHeaders() {{
    const headers = {{}};
    const tok = document.getElementById("token");
    if (tok && tok.value) {{
      headers["Authorization"] = "Bearer " + tok.value;
      headers["X-DSM-AE-Token"] = tok.value;
    }}
    return headers;
  }}

  const dd = document.getElementById("pack-dd");
  const toggle = document.getElementById("pack-toggle");
  const fullCb = document.getElementById("f-full-cb");

  function selectedPacks() {{
    return Array.from(document.querySelectorAll(".pack-cb:checked")).map((c) => c.value);
  }}
  function updatePackLabel() {{
    if (fullCb.checked) {{ toggle.textContent = "Full suite (all packs)"; return; }}
    const sel = selectedPacks();
    if (!sel.length) toggle.textContent = "Select packs… (default: all)";
    else if (sel.length <= 3) toggle.textContent = sel.join(", ");
    else toggle.textContent = sel.length + " packs selected";
  }}
  toggle.addEventListener("click", (ev) => {{ ev.preventDefault(); dd.classList.toggle("open"); }});
  document.addEventListener("click", (ev) => {{ if (!dd.contains(ev.target)) dd.classList.remove("open"); }});
  document.getElementById("pack-all").addEventListener("click", (ev) => {{
    ev.preventDefault();
    document.querySelectorAll(".pack-cb").forEach((c) => {{ c.checked = true; }});
    fullCb.checked = false; updatePackLabel(); persistForm();
  }});
  document.getElementById("pack-none").addEventListener("click", (ev) => {{
    ev.preventDefault();
    document.querySelectorAll(".pack-cb").forEach((c) => {{ c.checked = false; }});
    fullCb.checked = false; updatePackLabel(); persistForm();
  }});
  document.querySelectorAll(".pack-cb").forEach((c) => {{
    c.addEventListener("change", () => {{ fullCb.checked = false; updatePackLabel(); persistForm(); }});
  }});
  fullCb.addEventListener("change", () => {{
    if (fullCb.checked) document.querySelectorAll(".pack-cb").forEach((c) => {{ c.checked = false; }});
    updatePackLabel(); persistForm();
  }});

  function persistForm() {{
    const data = {{}};
    document.querySelectorAll("[data-persist]").forEach((el) => {{
      data[el.getAttribute("data-persist")] = el.type === "checkbox" ? el.checked : el.value;
    }});
    data.packs = selectedPacks();
    data.full_suite = fullCb.checked;
    try {{ sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data)); }} catch (e) {{}}
  }}
  function restoreForm() {{
    let data = null;
    try {{ data = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "null"); }} catch (e) {{}}
    if (!data) return;
    document.querySelectorAll("[data-persist]").forEach((el) => {{
      const k = el.getAttribute("data-persist");
      if (!(k in data)) return;
      if (el.type === "checkbox") el.checked = !!data[k];
      else if (data[k] != null) el.value = data[k];
    }});
    if (Array.isArray(data.packs)) {{
      const set = new Set(data.packs);
      document.querySelectorAll(".pack-cb").forEach((c) => {{ c.checked = set.has(c.value); }});
    }}
    fullCb.checked = !!data.full_suite;
    updatePackLabel();
  }}

  function esc(s) {{
    return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
      .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  }}
  function badge(status) {{
    return '<span class="status st-' + esc(status) + '">' + esc(status) + "</span>";
  }}
  function progCell(job) {{
    const p = job.progress || null;
    if (!p) {{
      if (job.status === "queued") return '<div class="prog">waiting…</div>';
      if (job.status === "succeeded") return '<div class="prog">100%</div>';
      return '<div class="prog">—</div>';
    }}
    const pct = (p.percent != null) ? p.percent : (p.total ? Math.round(100*(p.done||0)/p.total) : 0);
    return '<div class="prog">' + esc(String(pct)) + "% · " + esc(p.message || "") +
      '<div class="prog-bar"><i style="width:' + pct + '%"></i></div></div>';
  }}

  function renderJobs(jobs) {{
    const tbody = document.getElementById("jobs-body");
    if (!jobs || !jobs.length) {{
      tbody.innerHTML = '<tr><td colspan="10" style="color:#666">No jobs yet — enqueue below.</td></tr>';
      return;
    }}
    tbody.innerHTML = jobs.map((j) => {{
      const packs = (j.packs && j.packs.length) ? j.packs.join(",") : "—";
      let err = j.error || "";
      if (err.length > 100) err = err.slice(0, 100) + "…";
      let actions = "";
      if (j.status === "queued")
        actions = '<button type="button" class="action" data-act="cancel" data-id="'+esc(j.id)+'">cancel</button>';
      else if (j.status === "failed" || j.status === "cancelled")
        actions = '<button type="button" class="action" data-act="retry" data-id="'+esc(j.id)+'">retry</button>';
      const endpoint = j.api_base ? (' <span class="hint" title="'+esc(j.api_base)+'">↗</span>') : "";
      return "<tr>" +
        '<td><code title="'+esc(j.id)+'">'+esc(j.id.slice(0,8))+"</code></td>" +
        "<td>"+badge(j.status)+"</td>" +
        "<td><code>"+esc(j.model)+"</code>"+endpoint+"</td>" +
        "<td>"+progCell(j)+"</td>" +
        "<td>"+esc(j.k)+"</td>" +
        '<td style="max-width:160px;overflow:hidden;text-overflow:ellipsis">'+esc(packs)+"</td>" +
        "<td>"+esc(j.label||"")+"</td>" +
        '<td style="font-size:11px">'+esc(j.created_at||"")+"</td>" +
        '<td style="font-size:11px;color:#a00">'+esc(err)+"</td>" +
        "<td>"+actions+"</td></tr>";
    }}).join("");
  }}

  async function refreshJobs() {{
    try {{
      const res = await fetch(API_JOBS + "?limit=100", {{ cache: "no-store" }});
      if (!res.ok) throw new Error("HTTP " + res.status);
      renderJobs(await res.json());
      const u = document.getElementById("jobs-updated");
      u.textContent = "· updated " + new Date().toLocaleTimeString();
      u.className = "hint ok";
    }} catch (e) {{
      const u = document.getElementById("jobs-updated");
      u.textContent = "· refresh failed";
      u.className = "hint err";
    }}
  }}

  async function jobAction(act, id, btn) {{
    if (AUTH_REQUIRED) {{
      const tok = document.getElementById("token");
      if (!tok || !tok.value) {{ flash("Token required for " + act, false); return; }}
    }}
    if (btn) btn.disabled = true;
    try {{
      const res = await fetch(API_JOBS + "/" + encodeURIComponent(id) + "/" + act, {{
        method: "POST", headers: authHeaders(),
      }});
      if (!res.ok) {{
        flash(act + " failed: " + res.status + " " + await res.text(), false);
        await refreshJobs(); return;
      }}
      flash(act + " ok", true);
      await refreshJobs();
    }} catch (e) {{
      flash(String(e), false); await refreshJobs();
    }} finally {{ if (btn) btn.disabled = false; }}
  }}

  document.getElementById("jobs-body").addEventListener("click", (ev) => {{
    const btn = ev.target.closest("button[data-act]");
    if (!btn) return;
    jobAction(btn.getAttribute("data-act"), btn.getAttribute("data-id"), btn);
  }});

  document.getElementById("test-conn-btn").addEventListener("click", async () => {{
    if (AUTH_REQUIRED) {{
      const tok = document.getElementById("token");
      if (!tok || !tok.value) {{ connMsg("Token required", false); return; }}
    }}
    const btn = document.getElementById("test-conn-btn");
    btn.disabled = true; connMsg("Testing…", true);
    try {{
      const body = {{
        model: (document.getElementById("f-model").value || "").trim(),
        api_base: (document.getElementById("f-api-base").value || "").trim() || null,
        api_key: (document.getElementById("f-api-key").value || "").trim() || null,
        timeout: parseFloat(document.getElementById("f-timeout").value || "30"),
        num_retries: 0,
      }};
      if (!body.model) {{ connMsg("Enter a model id", false); return; }}
      const res = await fetch(API_TEST, {{
        method: "POST",
        headers: Object.assign({{"Content-Type":"application/json"}}, authHeaders()),
        body: JSON.stringify(body),
      }});
      const data = await res.json().catch(() => ({{ ok: false, message: res.statusText }}));
      if (!res.ok && data.detail) {{
        connMsg(typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail), false);
        return;
      }}
      connMsg(data.message || (data.ok ? "OK" : "Failed"), !!data.ok);
    }} catch (e) {{
      connMsg(String(e), false);
    }} finally {{ btn.disabled = false; }}
  }});

  const form = document.getElementById("enqueue-form");
  form.addEventListener("input", persistForm);
  form.addEventListener("change", persistForm);
  form.addEventListener("submit", async (ev) => {{
    ev.preventDefault(); persistForm();
    if (AUTH_REQUIRED) {{
      const tok = document.getElementById("token");
      if (!tok || !tok.value) {{ flash("Token required to enqueue", false); return; }}
    }}
    const btn = document.getElementById("enqueue-btn");
    btn.disabled = true;
    try {{
      const packs = fullCb.checked ? null : selectedPacks();
      const body = {{
        model: (document.getElementById("f-model").value || "").trim(),
        packs: packs && packs.length ? packs : null,
        full_suite: fullCb.checked,
        k: parseInt(document.getElementById("f-k").value || "3", 10),
        concurrency: parseInt(document.getElementById("f-concurrency").value || "1", 10),
        priority: parseInt(document.getElementById("f-priority").value || "0", 10),
        label: ((document.getElementById("f-label").value || "").trim() || null),
        api_base: (document.getElementById("f-api-base").value || "").trim() || null,
        api_key: (document.getElementById("f-api-key").value || "").trim() || null,
        timeout: parseFloat(document.getElementById("f-timeout").value || "120"),
        num_retries: 2,
      }};
      const res = await fetch(API_JOBS, {{
        method: "POST",
        headers: Object.assign({{"Content-Type":"application/json"}}, authHeaders()),
        body: JSON.stringify(body),
      }});
      if (!res.ok) {{
        flash("Enqueue failed: " + res.status + " " + await res.text(), false);
        return;
      }}
      const job = await res.json();
      flash("Enqueued " + (job.id || "").slice(0, 8) + " · " + job.model, true);
      document.getElementById("f-label").value = "";
      persistForm();
      await refreshJobs();
    }} catch (e) {{
      flash(String(e), false);
    }} finally {{ btn.disabled = false; }}
  }});

  restoreForm();
  updatePackLabel();
  refreshJobs();
  setInterval(refreshJobs, POLL_MS);
}})();
</script>
</body>
</html>
"""
