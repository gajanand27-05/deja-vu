"""Déjà CLI surface.

Commands are stubbed and implemented phase-by-phase. Each stub prints the phase
that owns it so an early user run is self-documenting.
"""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from deja import __version__
from deja.config import load_settings
from deja.store import prepare_cognee_env


app = typer.Typer(
    name="deja",
    help="A coding mentor that remembers you. Built on Cognee.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _bootstrap() -> None:
    """Run at the top of every command that touches cognee."""
    settings = load_settings()
    prepare_cognee_env(settings.data_dir)


def _stub(command: str, phase: str) -> None:
    console.print(
        Panel.fit(
            f"[yellow]{command}[/yellow] lands in [bold]{phase}[/bold].\n"
            "See CLAUDE.md for the phase plan.",
            title="not implemented yet",
            border_style="yellow",
        )
    )


@app.command()
def version() -> None:
    """Print version."""
    console.print(f"deja {__version__}")


@app.command()
def doctor() -> None:
    """Verify env + Cognee connectivity + seed integrity."""
    s = load_settings()
    console.print(f"[bold]data_dir[/bold]  {s.data_dir}")
    console.print(f"[bold]learner[/bold]   {s.learner_name}")
    console.print(f"[bold]llm[/bold]       {s.llm_provider}:{s.llm_model}")
    console.print(f"[bold]llm key[/bold]   {'set' if s.has_llm_key else '[red]missing[/red]'}")
    console.print("\nFuller checks (Cognee ping, seed integrity) land in later phases.")


@app.command()
def seed() -> None:
    """Produce the demo BEFORE state (spec §6)."""
    _bootstrap()
    from deja.commands.seed_cmd import seed as run_seed

    with console.status("[cyan]seeding graph…[/cyan]", spinner="dots"):
        summary = asyncio.run(run_seed(wipe_first=True))

    tbl = Table(title="seed complete — BEFORE state", show_header=True, header_style="bold")
    tbl.add_column("field")
    tbl.add_column("value")
    tbl.add_row("learner", summary["learner"])
    tbl.add_row("concepts", ", ".join(summary["concepts"]))
    tbl.add_row(
        "skills",
        "\n".join(f"{k}: {v}" for k, v in summary["skills"].items()),
    )
    tbl.add_row("sessions", ", ".join(summary["sessions"]))
    tbl.add_row("mistakes", ", ".join(summary["mistakes"]))
    tbl.add_row("edges_added", str(summary["edges_added"]))
    tbl.add_row(
        "SAME_FAMILY_AS edges",
        f"[green]{summary['same_family_as_edges']}[/green] (invariant — memify creates these)",
    )
    console.print(tbl)


@app.command()
def start() -> None:
    """Cold open — recall who you are (spec §5, Scene 1)."""
    _bootstrap()
    from deja.commands.start_cmd import build_cold_open, render_cold_open

    with console.status("[cyan]recalling…[/cyan]", spinner="dots"):
        cold = asyncio.run(build_cold_open())

    console.print(
        Panel.fit(
            render_cold_open(cold),
            title=f"deja — {cold.learner_name}",
            border_style="cyan",
        )
    )


@app.command()
def chat() -> None:
    """Coaching loop with thumbs-up feedback (Phase 3, Scene 2)."""
    _stub("chat", "Phase 3")


@app.command()
def memify() -> None:
    """Re-organize the graph — the headline moment (Phase 4, Scene 3)."""
    _stub("memify", "Phase 4")


@app.command()
def forget() -> None:
    """Decay mastered skills + prune deprecated concepts (Phase 5, Scene 4)."""
    _stub("forget", "Phase 5")


@app.command()
def ui() -> None:
    """Serve the live graph viewer (Phase 6)."""
    _stub("ui", "Phase 6")


@app.command()
def capture() -> None:
    """Write before/after PNG fallback captures (Phase 6)."""
    _stub("capture", "Phase 6")


if __name__ == "__main__":
    app()
