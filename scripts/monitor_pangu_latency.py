#!/usr/bin/env python3
"""Probe Beta_pangu endpoints for latency / tokens-per-second while benchmark runs.

Writes CSV + human log; also samples trial-dir completion rates from work/.
"""
from __future__ import annotations

import csv
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
LOG = ROOT / "logs" / "pangu_latency_monitor.log"
CSV = ROOT / "logs" / "pangu_latency_monitor.csv"
MODELS = ["Beta_pangu_92b", "Beta_pangu_505b"]
INTERVAL_S = 45
PROBE_PROMPT = "Reply with exactly: ok"


def load_deployments(path: Path) -> dict[str, dict]:
    data = yaml.safe_load(path.read_text())
    out = {}
    for e in data.get("model_list") or []:
        name = e.get("model_name")
        if name in MODELS:
            out[name] = dict(e.get("litellm_params") or {})
    return out


def probe(name: str, params: dict) -> dict:
    import litellm

    litellm.drop_params = True
    model = params.get("model") or name
    api_base = params.get("api_base")
    api_key = params.get("api_key")
    # openai-compatible proxy
    if api_base and "/" not in model:
        model_id = f"openai/{model}"
    else:
        model_id = model

    t0 = time.perf_counter()
    err = None
    usage = {}
    content = ""
    try:
        resp = litellm.completion(
            model=model_id,
            messages=[{"role": "user", "content": PROBE_PROMPT}],
            temperature=0,
            max_tokens=16,
            api_base=api_base,
            api_key=api_key,
            timeout=120,
            num_retries=0,
        )
        msg = resp.choices[0].message
        content = (msg.content or "")[:80]
        if getattr(resp, "usage", None):
            usage = {
                "prompt_tokens": float(getattr(resp.usage, "prompt_tokens", 0) or 0),
                "completion_tokens": float(
                    getattr(resp.usage, "completion_tokens", 0) or 0
                ),
            }
    except Exception as e:
        err = f"{type(e).__name__}: {e}"[:300]
    elapsed = time.perf_counter() - t0
    pt = usage.get("prompt_tokens", 0.0)
    ct = usage.get("completion_tokens", 0.0)
    total = pt + ct
    tps = (total / elapsed) if elapsed > 0 and total > 0 else 0.0
    ctps = (ct / elapsed) if elapsed > 0 and ct > 0 else 0.0
    return {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "model": name,
        "ok": err is None,
        "latency_s": round(elapsed, 3),
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": total,
        "tokens_per_s": round(tps, 2),
        "completion_tokens_per_s": round(ctps, 2),
        "error": err or "",
        "preview": content.replace("\n", " "),
    }


def trial_progress() -> dict[str, int]:
    prog = {}
    for m in MODELS:
        d = ROOT / "work" / f"fs_{m}_full"
        if not d.exists():
            prog[m] = 0
            continue
        prog[m] = sum(1 for _ in d.glob("*/*") if _.is_dir())
    return prog


def summarize(rows: list[dict], model: str) -> str:
    xs = [r for r in rows if r["model"] == model and r["ok"]]
    if not xs:
        fails = [r for r in rows if r["model"] == model and not r["ok"]]
        return f"{model}: no successful probes yet (fails={len(fails)})"
    lats = [r["latency_s"] for r in xs]
    tps = [r["tokens_per_s"] for r in xs if r["tokens_per_s"] > 0]
    ctps = [r["completion_tokens_per_s"] for r in xs if r["completion_tokens_per_s"] > 0]
    def stats(a):
        if not a:
            return "n/a"
        med = statistics.median(a)
        mean = statistics.fmean(a)
        mn, mx = min(a), max(a)
        sd = statistics.pstdev(a) if len(a) > 1 else 0.0
        return f"n={len(a)} mean={mean:.2f} med={med:.2f} min={mn:.2f} max={mx:.2f} sd={sd:.2f}"
    last = xs[-1]
    return (
        f"{model}: latency_s[{stats(lats)}] "
        f"tok/s[{stats(tps)}] "
        f"out_tok/s[{stats(ctps)}] "
        f"| last lat={last['latency_s']}s tps={last['tokens_per_s']} ok={last['ok']}"
    )


def main() -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    deps = load_deployments(ROOT / "models.yaml")
    if not deps:
        print("No pangu deployments in models.yaml", flush=True)
        return

    write_header = not CSV.exists()
    fcsv = CSV.open("a", newline="", encoding="utf-8")
    writer = csv.DictWriter(
        fcsv,
        fieldnames=[
            "ts",
            "model",
            "ok",
            "latency_s",
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "tokens_per_s",
            "completion_tokens_per_s",
            "error",
            "preview",
            "trial_dirs",
        ],
    )
    if write_header:
        writer.writeheader()

    history: list[dict] = []
    with LOG.open("a", encoding="utf-8") as flog:
        flog.write(f"\n===== latency monitor start {datetime.now().isoformat()} =====\n")
        flog.flush()
        print(f"Monitoring {list(deps)} every {INTERVAL_S}s → {LOG}", flush=True)
        while True:
            # stop if batch done and we have some history after completion
            batch_done = "ALL COMPLETE" in (ROOT / "logs" / "full_suite_pangu.log").read_text(
                encoding="utf-8", errors="replace"
            ) if (ROOT / "logs" / "full_suite_pangu.log").exists() else False
            prog = trial_progress()
            for name, params in deps.items():
                row = probe(name, params)
                row["trial_dirs"] = prog.get(name, 0)
                history.append(row)
                writer.writerow(row)
                fcsv.flush()
                line = (
                    f"{row['ts']} {name} ok={row['ok']} lat={row['latency_s']}s "
                    f"pt={row['prompt_tokens']} ct={row['completion_tokens']} "
                    f"tps={row['tokens_per_s']} out_tps={row['completion_tokens_per_s']} "
                    f"trials={row['trial_dirs']}"
                )
                if row["error"]:
                    line += f" ERR={row['error'][:120]}"
                flog.write(line + "\n")
                print(line, flush=True)
            for name in deps:
                s = summarize(history, name)
                flog.write("  SUMMARY " + s + "\n")
                print("  SUMMARY " + s, flush=True)
            flog.write(f"  progress trial_dirs={prog}\n")
            flog.flush()
            if batch_done:
                # one more summary then exit
                flog.write("===== batch complete; monitor exiting =====\n")
                flog.flush()
                print("Batch complete; exiting monitor", flush=True)
                break
            time.sleep(INTERVAL_S)
    fcsv.close()


if __name__ == "__main__":
    main()
