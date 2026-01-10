"""CLI entry point for Claudestine orchestrator."""

import asyncio
from pathlib import Path

import click

from claudestine.models import OrchestratorConfig, OrchestratorState
from claudestine.orchestrator import Orchestrator
from claudestine.parsers.plan import PlanParser
from claudestine.tui import ClaudestineApp


@click.group()
@click.version_option(version="0.1.0", prog_name="claudestine")
def main():
    """Claudestine - Automated plan implementation orchestrator for Claude Code.

    Wraps Claude Code's /implement_plan skill and handles:

    \b
    1. Running /implement_plan until completion or manual verification
    2. Automated verification (Playwright MCP, uv run, service tests)
    3. Updating plan summary for session continuity
    4. Git commit (conventional commits, no watermark) and push
    5. Clearing session and looping
    """
    pass


def _resolve_working_dir(plan_path: Path, working_dir: Path | None) -> Path:
    """Resolve the working directory from plan path."""
    if working_dir is not None:
        return working_dir.resolve()

    # Default: plan's parent, but if in thoughts/ directory, go up to project root
    resolved = plan_path.parent
    if "thoughts" in resolved.parts:
        thoughts_index = resolved.parts.index("thoughts")
        resolved = Path(*resolved.parts[:thoughts_index])

    return resolved.resolve()


@main.command()
@click.argument("plan_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--working-dir", "-w",
    type=click.Path(exists=True, path_type=Path),
    default=None,
    help="Working directory for Claude Code. Defaults to project root.",
)
@click.option(
    "--confidence-threshold", "-c",
    type=float,
    default=0.8,
    help="Minimum confidence to continue (0-1). Default: 0.8",
)
@click.option(
    "--auto-commit/--no-auto-commit",
    default=True,
    help="Automatically commit after each iteration. Default: enabled",
)
@click.option(
    "--auto-push/--no-auto-push",
    default=True,
    help="Automatically push after commit. Default: enabled",
)
@click.option(
    "--playwright/--no-playwright",
    default=True,
    help="Use Playwright MCP for verification. Default: enabled",
)
@click.option(
    "--headless",
    is_flag=True,
    default=False,
    help="Run without TUI (console output only).",
)
def run(
    plan_path: Path,
    working_dir: Path | None,
    confidence_threshold: float,
    auto_commit: bool,
    auto_push: bool,
    playwright: bool,
    headless: bool,
):
    """Run plan implementation with the orchestrator.

    \b
    PLAN_PATH: Path to the markdown implementation plan file.

    \b
    Examples:
        claudestine run thoughts/shared/plans/my-plan.md
        claudestine run plan.md --headless --no-auto-push
        claudestine run plan.md -c 0.9 --no-playwright
    """
    plan_path = plan_path.resolve()
    working_dir = _resolve_working_dir(plan_path, working_dir)

    config = OrchestratorConfig(
        plan_path=plan_path,
        working_dir=working_dir,
        confidence_threshold=confidence_threshold,
        auto_commit=auto_commit,
        auto_push=auto_push,
        playwright_enabled=playwright,
    )

    click.echo(f"Plan: {plan_path.name}")
    click.echo(f"Working dir: {working_dir}")
    click.echo(f"Confidence threshold: {confidence_threshold:.0%}")
    click.echo(f"Auto-commit: {auto_commit}, Auto-push: {auto_push}")
    click.echo()

    if headless:
        _run_headless(config)
    else:
        _run_tui(config)


def _run_headless(config: OrchestratorConfig) -> None:
    """Run orchestrator in headless mode (console output)."""
    click.secho("Starting Claudestine (headless mode)", fg="cyan")
    click.echo()

    orchestrator = Orchestrator(config)

    try:
        success = asyncio.run(orchestrator.run())
        click.echo()
        if success:
            click.secho("Plan implementation complete!", fg="green", bold=True)
        else:
            click.secho("Orchestration stopped before completion.", fg="yellow")
            raise SystemExit(1)
    except KeyboardInterrupt:
        click.echo()
        click.secho("Interrupted by user.", fg="yellow")
        raise SystemExit(130)


def _run_tui(config: OrchestratorConfig) -> None:
    """Run orchestrator with TUI."""
    # Parse plan for initial state
    plan_parser = PlanParser(config.plan_path)
    plan = plan_parser.parse()

    state = OrchestratorState(
        plan=plan,
        config=config,
    )

    # Create orchestrator and app
    orchestrator = Orchestrator(config)
    app = ClaudestineApp(state=state)

    # Wire orchestrator to use app for UI callbacks
    orchestrator.ui = app

    # Set orchestrator on app so it can start it
    app.set_orchestrator(orchestrator)

    # Run the TUI (orchestration starts in on_mount via worker)
    app.run()


@main.command()
@click.argument("plan_path", type=click.Path(exists=True, path_type=Path))
def preview(plan_path: Path):
    """Preview the parsed plan structure without running.

    \b
    PLAN_PATH: Path to the markdown implementation plan file.
    """
    plan_path = plan_path.resolve()
    parser = PlanParser(plan_path)
    plan = parser.parse()

    click.echo(f"Title: {plan.title}")
    click.echo(f"Path: {plan.path}")
    click.echo(f"Progress: {plan.progress_percentage:.1f}%")
    click.echo(f"Current Phase: {plan.current_phase_index + 1}")
    click.echo()
    click.echo("Phases:")
    for i, phase in enumerate(plan.phases):
        status_icon = {
            "pending": "○",
            "in_progress": "●",
            "completed": "✓",
            "failed": "✗",
            "skipped": "⊘",
        }.get(phase.status.value, "?")

        current = " (current)" if i == plan.current_phase_index else ""
        click.echo(f"  {status_icon} {phase.name}{current}")

        if phase.steps:
            click.echo(f"    Steps: {len(phase.steps)}")
        if phase.success_criteria:
            click.echo(f"    Success criteria: {len(phase.success_criteria)}")


@main.command()
def version():
    """Show version information."""
    from claudestine import __version__

    click.echo(f"Claudestine v{__version__}")
    click.echo("Automated plan implementation orchestrator for Claude Code")
    click.echo()
    click.echo("Loop workflow:")
    click.echo("  1. /implement_plan @{plan} - stop for manual verification")
    click.echo("  2. Automated verification (Playwright/uv/docker)")
    click.echo("  3. Update plan summary")
    click.echo("  4. Git commit + push (conventional, no watermark)")
    click.echo("  5. Clear session, repeat")


if __name__ == "__main__":
    main()
