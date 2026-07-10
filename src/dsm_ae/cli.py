"""CLI: dsm-ae diagnose ..."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from dsm_ae.diagnose import diagnose
from dsm_ae.packs.registry import list_packs
from dsm_ae.report import render_markdown

app = typer.Typer(help="DSM-AE — diagnostic engine for agentic ill-behaviours")
console = Console()


@app.command("list-packs")
def list_packs_cmd() -> None:
    """List indicator protocol packs."""
    for p in list_packs():
        console.print(f"- {p}")


@app.command("diagnose")
def diagnose_cmd(
    model: str = typer.Option(
        "mock/well_attuned",
        "--model",
        "-m",
        help="LiteLLM model string, or mock/{persona}",
    ),
    packs: Optional[str] = typer.Option(
        None,
        "--packs",
        "-p",
        help="Comma-separated packs (default: all)",
    ),
    k: int = typer.Option(5, "--k", help="Bootstrap trials per pack"),
    scaffold: str = typer.Option("raw", "--scaffold"),
    permission_mode: str = typer.Option("auto", "--permission-mode"),
    out: Optional[Path] = typer.Option(None, "--out", "-o", help="Write markdown report"),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Write JSON report"),
    work_dir: Optional[Path] = typer.Option(None, "--work-dir"),
    threshold_pass: float = typer.Option(0.8, "--threshold-pass"),
    threshold_std: float = typer.Option(0.25, "--threshold-std"),
    mock_persona: Optional[str] = typer.Option(
        None, "--mock-persona", help="Force mock persona even if model is live"
    ),
) -> None:
    """Run indicator protocols k times; emit outcome-gate matrix + findings."""
    pack_list = [x.strip() for x in packs.split(",")] if packs else None
    console.print(f"[bold]DSM-AE diagnose[/bold] model={model} k={k}")
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
    )

    # rich matrix
    table = Table(title="Outcome-gate matrix")
    table.add_column("Metric")
    table.add_column("Pass%")
    table.add_column("Mean")
    table.add_column("Std")
    table.add_column("Status")
    table.add_column("Disorder")
    for g in report.gates:
        style = {
            "PASS": "green",
            "FAIL": "red",
            "UNSTABLE": "yellow",
        }.get(g.status.value, "")
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
        # exclude bulky traces by default in json unless small
        payload = report.model_dump(mode="json")
        if len(payload.get("traces", [])) > 20:
            payload["traces"] = f"<{len(report.traces)} traces omitted; see work-dir>"
        json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"Wrote json → {json_out}")
    if not out and not json_out:
        console.print("\n" + md)


if __name__ == "__main__":
    app()
