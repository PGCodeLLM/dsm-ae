"""CLI: dsm-ae diagnose ..."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from dsm_ae.diagnose import diagnose
from dsm_ae.packs.registry import list_packs, pack_pattern_index, PACKS
from dsm_ae.report import render_markdown

app = typer.Typer(help="DSM-AE — diagnostic engine for agentic ill-behaviours")
console = Console()


def _print_report(report, out: Optional[Path], json_out: Optional[Path]) -> None:
    table = Table(title="Outcome-gate matrix")
    table.add_column("Metric")
    table.add_column("Pass%")
    table.add_column("Mean")
    table.add_column("Std")
    table.add_column("Status")
    table.add_column("Disorder")
    for g in report.gates:
        style = {"PASS": "green", "FAIL": "red", "UNSTABLE": "yellow"}.get(g.status.value, "")
        table.add_row(
            g.metric_id,
            f"{g.pass_rate:.0%}",
            f"{g.mean:.3f}",
            f"{g.std:.3f}",
            f"[{style}]{g.status.value}[/{style}]" if style else g.status.value,
            "yes" if g.disorder else "no",
        )
    console.print(table)
    console.print("\n[bold]Findings[/bold]")
    for f in report.findings:
        mark = "[red]PRESENT[/red]" if f.present else "[green]absent[/green]"
        console.print(f"  {f.code} {f.name}: {mark} ({f.severity})")
    md = render_markdown(report)
    if out:
        out.write_text(md, encoding="utf-8")
        console.print(f"\nWrote markdown → {out}")
    if json_out:
        payload = report.model_dump(mode="json")
        if len(payload.get("traces", [])) > 20:
            payload["traces"] = f"<{len(report.traces)} traces omitted>"
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"Wrote json → {json_out}")
    if not out and not json_out:
        console.print("\n" + md)


@app.command("list-packs")
def list_packs_cmd() -> None:
    """List indicator protocol packs."""
    for pid in list_packs():
        p = PACKS[pid]
        console.print(f"- [bold]{pid}[/bold]: {p.name} ({', '.join(p.patterns)})")


@app.command("coverage")
def coverage_cmd(
    patterns_json: Path = typer.Option(
        Path("taxonomy/patterns.json"), "--patterns", help="Taxonomy patterns.json"
    ),
    out: Optional[Path] = typer.Option(None, "--out", "-o"),
) -> None:
    """Report what fraction of taxonomy patterns are wired to indicator packs."""
    patterns = json.loads(patterns_json.read_text(encoding="utf-8"))
    idx = pack_pattern_index()
    wired = [p for p in patterns if p.get("code") in idx]
    missing = [p for p in patterns if p.get("code") not in idx]
    lines = [
        f"# DSM-AE Coverage",
        "",
        f"Taxonomy patterns: **{len(patterns)}**",
        f"Wired to ≥1 pack: **{len(wired)}** ({100*len(wired)/max(len(patterns),1):.1f}%)",
        f"Unwired: **{len(missing)}**",
        "",
        "## Packs",
        "",
    ]
    for pid in list_packs():
        p = PACKS[pid]
        lines.append(f"- `{pid}` → {', '.join(f'`{c}`' for c in p.patterns)}")
    lines.append("")
    lines.append("## Unwired codes (first 40)")
    lines.append("")
    for p in missing[:40]:
        lines.append(f"- `{p.get('code')}` {p.get('name')}")
    text = "\n".join(lines) + "\n"
    if out:
        out.write_text(text, encoding="utf-8")
        console.print(f"Wrote {out}")
    console.print(text)
    console.print(f"[bold]Coverage:[/bold] {len(wired)}/{len(patterns)}")


@app.command("diagnose")
def diagnose_cmd(
    model: str = typer.Option("mock/well_attuned", "--model", "-m"),
    packs: Optional[str] = typer.Option(None, "--packs", "-p"),
    k: int = typer.Option(5, "--k", help="Bootstrap trials per pack"),
    scaffold: str = typer.Option("raw", "--scaffold"),
    permission_mode: str = typer.Option("auto", "--permission-mode"),
    out: Optional[Path] = typer.Option(None, "--out", "-o"),
    json_out: Optional[Path] = typer.Option(None, "--json"),
    work_dir: Optional[Path] = typer.Option(None, "--work-dir"),
    threshold_pass: float = typer.Option(0.8, "--threshold-pass"),
    threshold_std: float = typer.Option(0.25, "--threshold-std"),
    mock_persona: Optional[str] = typer.Option(None, "--mock-persona"),
    models_yaml: Optional[Path] = typer.Option(None, "--models-yaml"),
    api_base: Optional[str] = typer.Option(None, "--api-base"),
    api_key: Optional[str] = typer.Option(None, "--api-key", envvar="DSM_AE_API_KEY"),
    concurrency: int = typer.Option(
        1, "--concurrency", "-j", help="Parallel pack×trial jobs (default 1=sequential)"
    ),
    rpm: Optional[float] = typer.Option(
        None, "--rpm", help="Max job starts per minute (default: models.yaml rpm if any)"
    ),
) -> None:
    """Run indicator protocols k times; emit outcome-gate matrix + findings."""
    pack_list = [x.strip() for x in packs.split(",")] if packs else None
    console.print(
        f"[bold]DSM-AE diagnose[/bold] model={model} k={k} "
        f"concurrency={concurrency} yaml={models_yaml}"
    )
    report = diagnose(
        model=model,
        packs=pack_list,
        k=k,
        scaffold=scaffold,
        permission_mode=permission_mode,
        work_dir=work_dir,
        mock_persona=mock_persona,
        threshold_pass=threshold_pass,
        threshold_std=threshold_std,
        models_yaml=models_yaml,
        api_base=api_base,
        api_key=api_key,
        concurrency=concurrency,
        rpm=rpm,
    )
    _print_report(report, out, json_out)


@app.command("diagnose-batch")
def diagnose_batch_cmd(
    models: str = typer.Option(..., "--models", help="Comma-separated model ids"),
    packs: Optional[str] = typer.Option(None, "--packs", "-p"),
    k: int = typer.Option(3, "--k"),
    models_yaml: Optional[Path] = typer.Option(None, "--models-yaml"),
    concurrency: int = typer.Option(1, "--concurrency", "-j"),
    out_dir: Path = typer.Option(Path("reports"), "--out-dir"),
    rpm: Optional[float] = typer.Option(None, "--rpm"),
) -> None:
    """Run diagnose for multiple models sequentially (stable)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pack_list = [x.strip() for x in packs.split(",")] if packs else None
    model_list = [m.strip() for m in models.split(",") if m.strip()]
    for model in model_list:
        safe = model.replace("/", "_")
        console.print(f"\n[bold cyan]=== {model} ===[/bold cyan]")
        report = diagnose(
            model=model,
            packs=pack_list,
            k=k,
            models_yaml=models_yaml,
            concurrency=concurrency,
            rpm=rpm,
            work_dir=out_dir / "work" / safe,
        )
        _print_report(report, out_dir / f"{safe}.md", out_dir / f"{safe}.json")



@app.command("html-report")
def html_report_cmd(
    input_dir: Path = typer.Option(Path("reports"), "--input", "-i", help="Dir of diagnosis JSON"),
    out: Path = typer.Option(Path("reports/dsm-ae-matrix.html"), "--out", "-o"),
    include_mock: bool = typer.Option(False, "--include-mock"),
    title: str = typer.Option("DSM-AE Multi-Model Report", "--title"),
) -> None:
    """Build HTML comparison matrix from diagnosis JSON files (NOT RUN for missing)."""
    import runpy
    import sys
    script = Path.cwd() / "scripts" / "json_to_html_report.py"
    if not script.exists():
        script = Path(__file__).resolve().parents[2] / "scripts" / "json_to_html_report.py"
    # Import as module for reliability under editable installs
    sys.path.insert(0, str(script.parent))
    from json_to_html_report import main as html_main  # type: ignore
    args = [str(input_dir), "-o", str(out), "--title", title]
    if include_mock:
        args.append("--include-mock")
    raise SystemExit(html_main(args))


if __name__ == "__main__":
    app()
