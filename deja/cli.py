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
    settings = load_settings()
    prepare_cognee_env(settings.data_dir)
    from deja.commands.seed_cmd import seed as run_seed

    with console.status("[cyan]seeding graph…[/cyan]", spinner="dots"):
        summary = asyncio.run(
            run_seed(wipe_first=True, snapshot_path=settings.snapshot_path)
        )

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
def chat(
    topic: str = typer.Option(
        "async error handling",
        "--topic",
        "-t",
        help="Concept name to coach on. Default matches the demo Scene 2 setup.",
    ),
    question: str = typer.Option(
        "My async task keeps mutating a shared list.",
        "--question",
        "-q",
        help="The learner's question or code paste, kept short for the demo.",
    ),
    feedback: str = typer.Option(
        "up",
        "--feedback",
        "-f",
        help="Simulated thumbs feedback for this turn: up | down | none.",
    ),
) -> None:
    """Coaching loop with thumbs-up feedback (Scene 2)."""
    _bootstrap()
    from deja.commands.chat_cmd import apply_feedback, coach_on_topic
    from deja.models.graph import Feedback

    settings = load_settings()
    prepare_cognee_env(settings.data_dir)

    async def _run() -> object:
        from deja.commands.chat_cmd import coach_on_topic as _coach
        result = await _coach(topic, question)
        from deja.store.graph_store import export_snapshot_to_file
        await export_snapshot_to_file(settings.snapshot_path)
        return result

    with console.status("[cyan]coaching…[/cyan]", spinner="dots"):
        turn = asyncio.run(_run())

    console.print(
        Panel(
            turn.message,
            title=f"deja — coaching on {turn.topic_concept}",
            border_style="cyan",
        )
    )

    try:
        fb = Feedback(feedback.lower())
    except ValueError:
        console.print(f"[red]unknown feedback '{feedback}'; skipping improve.[/red]")
        return

    if fb is Feedback.NONE:
        return

    async def _run_fb() -> dict:
        result = await apply_feedback(turn, fb)
        from deja.store.graph_store import export_snapshot_to_file
        await export_snapshot_to_file(settings.snapshot_path)
        return result

    changes = asyncio.run(_run_fb())
    if changes:
        tbl = Table(
            title=f"improve → {fb.value}",
            show_header=True,
            header_style="bold",
        )
        tbl.add_column("skill node")
        tbl.add_column("new mastery_weight")
        for node_id, w in changes.items():
            tbl.add_row(node_id[:8] + "…", f"{w:.2f}")
        console.print(tbl)


@app.command()
def memify() -> None:
    """Re-organize the graph — the headline moment (Scene 3)."""
    settings = load_settings()
    prepare_cognee_env(settings.data_dir)

    async def _run_memify() -> object:
        from deja.commands.memify_cmd import run_memify as _rm
        diff = await _rm()
        from deja.store.graph_store import export_snapshot_to_file
        await export_snapshot_to_file(settings.snapshot_path)
        return diff

    with console.status("[magenta]memifying…[/magenta]", spinner="dots"):
        diff = asyncio.run(_run_memify())

    if diff.is_empty:
        console.print(
            Panel.fit(
                "Nothing to re-organize — the graph is already coherent.",
                title="memify",
                border_style="yellow",
            )
        )
        return

    if diff.same_family_edges:
        tbl = Table(
            title="[bold magenta]SAME_FAMILY_AS — new cross-topic links[/bold magenta]",
            show_header=True,
            header_style="bold",
        )
        tbl.add_column("mistake A")
        tbl.add_column("concept A")
        tbl.add_column("mistake B")
        tbl.add_column("concept B")
        for a_key, b_key, c_a, c_b in diff.same_family_edges:
            tbl.add_row(a_key, c_a, b_key, c_b)
        console.print(tbl)

    if diff.related_concept_edges:
        tbl = Table(
            title="RELATED_TO — inferred concept relations",
            show_header=True,
            header_style="bold",
        )
        tbl.add_column("concept A")
        tbl.add_column("concept B")
        for a, b in diff.related_concept_edges:
            tbl.add_row(a, b)
        console.print(tbl)

    if diff.reweighted_skills:
        tbl = Table(
            title="skills reinforced by family links",
            show_header=True,
            header_style="bold",
        )
        tbl.add_column("concept")
        tbl.add_column("weight")
        for cref, (old, new) in diff.reweighted_skills.items():
            tbl.add_row(cref, f"{old:.2f} → {new:.2f}")
        console.print(tbl)


@app.command()
def forget(
    topic: str = typer.Option(
        None,
        "--topic",
        "-t",
        help="Force-decay a specific Concept's Skill (e.g. --topic recursion for Scene 4).",
    ),
) -> None:
    """Decay mastered skills + prune deprecated concepts (Scene 4)."""
    settings = load_settings()
    prepare_cognee_env(settings.data_dir)

    async def _run_forget() -> object:
        from deja.commands.forget_cmd import run_forget as _rf
        diff = await _rf(force_topic=topic)
        from deja.store.graph_store import export_snapshot_to_file
        await export_snapshot_to_file(settings.snapshot_path)
        return diff

    with console.status("[yellow]forgetting…[/yellow]", spinner="dots"):
        diff = asyncio.run(_run_forget())

    if diff.is_empty:
        console.print(
            Panel.fit(
                "Nothing to forget — no stale Skills, no deprecated Concepts.",
                title="forget",
                border_style="yellow",
            )
        )
        return

    if diff.decayed_skills:
        tbl = Table(
            title="[bold yellow]decayed (soft) — dropping from active recall[/bold yellow]",
            show_header=True,
            header_style="bold",
        )
        tbl.add_column("concept")
        tbl.add_column("weight")
        for cref, (old, new) in diff.decayed_skills.items():
            tbl.add_row(cref, f"{old:.2f} → {new:.2f}")
        console.print(tbl)

    if diff.pruned_concepts:
        tbl = Table(
            title="[bold red]pruned (hard) — deprecated concepts removed[/bold red]",
            show_header=True,
            header_style="bold",
        )
        tbl.add_column("concept")
        for c in diff.pruned_concepts:
            tbl.add_row(c)
        console.print(tbl)
        if diff.pruned_skills:
            console.print(
                f"  [dim]…and {len(diff.pruned_skills)} orphan Skill(s) pruned with them.[/dim]"
            )


@app.command()
def ui(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
) -> None:
    """Serve the live graph viewer at http://HOST:PORT/."""
    _bootstrap()
    import uvicorn

    from deja.ui.server import create_app

    console.print(
        Panel.fit(
            f"[bold cyan]déjà graph viewer[/bold cyan] → http://{host}:{port}/\n"
            "Run `deja memify` in another terminal to watch the SAME_FAMILY_AS edge appear.",
            border_style="cyan",
        )
    )
    uvicorn.run(create_app(), host=host, port=port, log_level="warning")


@app.command()
def capture(
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8765, "--port"),
) -> None:
    """Write BEFORE and AFTER PNGs for the Scene 3 fallback."""
    _bootstrap()
    from deja.commands.capture_cmd import capture_before_and_after

    before, after = capture_before_and_after(host=host, port=port)
    console.print(
        Panel.fit(
            f"BEFORE → {before}\nAFTER  → {after}",
            title="capture complete",
            border_style="green",
        )
    )


if __name__ == "__main__":
    app()
