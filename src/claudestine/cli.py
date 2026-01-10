"""Typer CLI for Claudestine."""

from pathlib import Path
from typing import Annotated, Optional

import editor
import questionary
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from claudestine import __version__
from claudestine.config import (
    RunConfig,
    Workflow,
    find_workflow,
    get_config_dir,
    get_project_config_dir,
    load_workflow,
)
from claudestine.ui import Console as ClaudestineConsole
from claudestine.workflow import WorkflowExecutor

app = typer.Typer(
    name="claudestine",
    help="Automated plan implementation orchestrator for Claude Code.",
    add_completion=False,
    invoke_without_command=True,
)

workflow_app = typer.Typer(
    name="workflow",
    help="Manage workflow templates.",
    no_args_is_help=True,
)
app.add_typer(workflow_app)

console = Console()


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context):
    """Interactive mode when no command is given."""
    if ctx.invoked_subcommand is None:
        _interactive_mode()


def _interactive_mode():
    """Boot into interactive selection mode."""
    console.print()
    console.print(Panel(
        Text.from_markup(
            f"[bold cyan]Claudestine[/bold cyan] [dim]v{__version__}[/dim]\n"
            "[dim]Automated plan implementation orchestrator[/dim]"
        ),
        border_style="cyan",
    ))
    console.print()

    # Step 1: Find and select plan
    cwd = Path.cwd()
    plan_patterns = [
        "**/thoughts/**/plans/*.md",
        "**/plans/*.md",
        "**/*-plan.md",
        "**/*_plan.md",
    ]

    plans = []
    for pattern in plan_patterns:
        plans.extend(cwd.glob(pattern))

    # Dedupe and sort
    plans = sorted(set(plans), key=lambda p: p.stat().st_mtime, reverse=True)[:20]

    if not plans:
        plan_path = questionary.path(
            "Enter path to plan file:",
            only_directories=False,
        ).ask()

        if not plan_path:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

        plan_path = Path(plan_path)
    else:
        choices = [
            questionary.Choice(
                title=f"{p.name} [dim]({p.parent.relative_to(cwd)})[/dim]",
                value=str(p),
            )
            for p in plans
        ]
        choices.append(questionary.Choice(title="[Enter custom path]", value="__custom__"))

        selected = questionary.select(
            "Select a plan:",
            choices=choices,
        ).ask()

        if not selected:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)

        if selected == "__custom__":
            plan_path = questionary.path(
                "Enter path to plan file:",
                only_directories=False,
            ).ask()
            if not plan_path:
                console.print("[yellow]Cancelled[/yellow]")
                raise typer.Exit(0)
            plan_path = Path(plan_path)
        else:
            plan_path = Path(selected)

    if not plan_path.exists():
        console.print(f"[red]File not found: {plan_path}[/red]")
        raise typer.Exit(1)

    # Step 2: Select workflow
    working_dir = _resolve_working_dir(plan_path, None)

    workflow_choices = [
        questionary.Choice(title="Default workflow", value="default"),
        questionary.Choice(title="Edit workflow before running", value="edit"),
        questionary.Choice(title="Select custom workflow file", value="custom"),
    ]

    # Check for existing workflows
    project_workflow = get_project_config_dir(working_dir) / "workflow.yaml"
    global_workflow = get_config_dir() / "workflow.yaml"

    if project_workflow.exists():
        workflow_choices.insert(0, questionary.Choice(
            title=f"Project workflow ({project_workflow.name})",
            value="project",
        ))

    if global_workflow.exists():
        workflow_choices.insert(1, questionary.Choice(
            title="Global workflow",
            value="global",
        ))

    workflow_choice = questionary.select(
        "Select workflow:",
        choices=workflow_choices,
    ).ask()

    if not workflow_choice:
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    # Load workflow based on choice
    if workflow_choice == "default":
        workflow = _get_default_workflow()
        edit_workflow = False
    elif workflow_choice == "project":
        workflow = Workflow.from_yaml(project_workflow)
        edit_workflow = False
    elif workflow_choice == "global":
        workflow = Workflow.from_yaml(global_workflow)
        edit_workflow = False
    elif workflow_choice == "edit":
        workflow = _get_default_workflow()
        edit_workflow = True
    elif workflow_choice == "custom":
        custom_path = questionary.path(
            "Enter path to workflow YAML:",
            only_directories=False,
        ).ask()
        if not custom_path:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Exit(0)
        workflow = Workflow.from_yaml(Path(custom_path))
        edit_workflow = False
    else:
        workflow = _get_default_workflow()
        edit_workflow = False

    # Edit workflow if requested
    if edit_workflow:
        yaml_content = workflow.to_yaml()
        edited = editor.edit(contents=yaml_content.encode())
        if edited:
            import yaml
            workflow = Workflow(**yaml.safe_load(edited))

    # Step 3: Confirm options
    auto_push = questionary.confirm(
        "Auto-push after commits?",
        default=True,
    ).ask()

    if auto_push is None:
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    # Step 4: Show summary and confirm
    console.print()
    console.print(Panel(
        f"[bold]Plan:[/bold] {plan_path.name}\n"
        f"[bold]Working dir:[/bold] {working_dir}\n"
        f"[bold]Workflow:[/bold] {workflow.name}\n"
        f"[bold]Auto-push:[/bold] {auto_push}",
        title="Configuration",
        border_style="cyan",
    ))

    if not questionary.confirm("Start execution?", default=True).ask():
        console.print("[yellow]Cancelled[/yellow]")
        raise typer.Exit(0)

    # Execute
    config = RunConfig(
        plan_path=plan_path.resolve(),
        working_dir=working_dir,
        auto_push=auto_push,
        dry_run=False,
        verbose=False,
    )

    ui = ClaudestineConsole(verbose=False)
    executor = WorkflowExecutor(workflow, config, ui)

    success = executor.execute()
    raise typer.Exit(0 if success else 1)


def _resolve_working_dir(plan_path: Path, working_dir: Path | None) -> Path:
    """Resolve working directory from plan path.

    Priority:
    1. Explicit working_dir if provided
    2. Git repository root
    3. Directory containing pyproject.toml or package.json
    4. Plan file's parent directory
    """
    if working_dir is not None:
        return working_dir.resolve()

    resolved = plan_path.parent.resolve()

    # If plan is in thoughts/ directory, go up to project root
    if "thoughts" in resolved.parts:
        thoughts_index = resolved.parts.index("thoughts")
        resolved = Path(*resolved.parts[:thoughts_index])
        return resolved

    # Try to find git root
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=resolved,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())
    except Exception:
        pass

    # Try to find project root by looking for pyproject.toml or package.json
    current = resolved
    while current != current.parent:
        if (current / "pyproject.toml").exists() or (current / "package.json").exists():
            return current
        current = current.parent

    return resolved


def _get_default_workflow() -> Workflow:
    """Get the default workflow template."""
    from claudestine.config import Step, StepType

    return Workflow(
        name="Implementation Loop",
        version=1,
        description="Default Claudestine workflow for plan implementation",
        steps=[
            Step(
                name="implement",
                type=StepType.CLAUDE,
                prompt="""Read @{plan_path} and implement ONLY the next incomplete phase (marked as "pending" or "in progress").
Do not implement multiple phases - stop after completing one phase.
Ensure to stop for any manual verification items listed in the phase.
Update the phase status to "complete" when done.""",
                stream=True,
            ),
            Step(
                name="verify",
                type=StepType.CLAUDE,
                prompt="""You do the manual testing for me. You may use either:
- Playwright MCP to test the UI
- uv run -c to run test commands
- Spin up services and test endpoints

Ensure everything is working. Report success/failure with details. Pause after verification.""",
                stream=True,
            ),
            Step(
                name="update_summary",
                type=StepType.CLAUDE,
                prompt="""Update the summary at the top of the plan ({plan_path}) so the next
session can understand and continue. Include:
- Current progress percentage
- What was completed this session
- What's next""",
                stream=True,
            ),
            Step(
                name="commit",
                type=StepType.CLAUDE,
                prompt="""Git commit with conventional commits on all the changes, outside of the things that are gitignored of course. Do not leave a claude code watermark. Push the changes.""",
                stream=True,
            ),
            Step(
                name="clear",
                type=StepType.INTERNAL,
                action="clear_session",
            ),
        ],
    )


@app.command()
def run(
    plan_path: Annotated[
        Path,
        typer.Argument(
            help="Path to the implementation plan markdown file.",
            exists=True,
            readable=True,
        ),
    ],
    working_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--working-dir", "-w",
            help="Working directory for Claude Code. Defaults to project root.",
        ),
    ] = None,
    workflow_path: Annotated[
        Optional[Path],
        typer.Option(
            "--workflow",
            help="Path to custom workflow YAML file.",
        ),
    ] = None,
    edit: Annotated[
        bool,
        typer.Option(
            "--edit", "-e",
            help="Edit workflow before running.",
        ),
    ] = False,
    auto_push: Annotated[
        bool,
        typer.Option(
            "--push/--no-push",
            help="Push after commit. Default: enabled.",
        ),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Show what would be executed without running.",
        ),
    ] = False,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Show verbose output.",
        ),
    ] = False,
):
    """Run plan implementation with the orchestrator.

    Examples:

        claudestine run plan.md

        claudestine run plan.md --edit

        claudestine run plan.md --no-push --dry-run
    """
    plan_path = plan_path.resolve()
    working_dir = _resolve_working_dir(plan_path, working_dir)

    # Load or create workflow
    try:
        if workflow_path:
            workflow = Workflow.from_yaml(workflow_path)
        else:
            workflow = load_workflow(working_dir, workflow_path)
    except FileNotFoundError:
        workflow = _get_default_workflow()

    # Edit workflow if requested
    if edit:
        yaml_content = workflow.to_yaml()
        edited = editor.edit(contents=yaml_content.encode())
        workflow = Workflow(**__import__("yaml").safe_load(edited))

    config = RunConfig(
        plan_path=plan_path,
        working_dir=working_dir,
        workflow_path=workflow_path,
        auto_push=auto_push,
        dry_run=dry_run,
        verbose=verbose,
    )

    console.print(Panel(
        f"[bold]Plan:[/bold] {plan_path.name}\n"
        f"[bold]Working dir:[/bold] {working_dir}\n"
        f"[bold]Workflow:[/bold] {workflow.name}\n"
        f"[bold]Auto-push:[/bold] {auto_push}",
        title="Claudestine",
        border_style="cyan",
    ))

    ui = ClaudestineConsole(verbose=verbose)
    executor = WorkflowExecutor(workflow, config, ui)

    if dry_run:
        executor.execute_dry_run()
        raise typer.Exit(0)

    success = executor.execute()
    raise typer.Exit(0 if success else 1)


@workflow_app.command("show")
def workflow_show(
    working_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--working-dir", "-w",
            help="Project directory to check for workflow.",
        ),
    ] = None,
):
    """Show the current workflow configuration."""
    working_dir = (working_dir or Path.cwd()).resolve()

    try:
        workflow = load_workflow(working_dir)
        workflow_path = find_workflow(working_dir)

        console.print(f"[dim]Source: {workflow_path}[/dim]\n")
        console.print(Syntax(workflow.to_yaml(), "yaml", theme="monokai"))

    except FileNotFoundError:
        console.print("[yellow]No workflow found. Using default.[/yellow]\n")
        workflow = _get_default_workflow()
        console.print(Syntax(workflow.to_yaml(), "yaml", theme="monokai"))


@workflow_app.command("edit")
def workflow_edit(
    scope: Annotated[
        str,
        typer.Option(
            "--scope", "-s",
            help="Scope: 'project' or 'global'.",
        ),
    ] = "project",
    working_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--working-dir", "-w",
            help="Project directory for project-scoped workflow.",
        ),
    ] = None,
):
    """Edit or create a workflow configuration."""
    working_dir = (working_dir or Path.cwd()).resolve()

    if scope == "project":
        workflow_path = get_project_config_dir(working_dir) / "workflow.yaml"
    else:
        workflow_path = get_config_dir() / "workflow.yaml"

    # Load existing or create default
    if workflow_path.exists():
        workflow = Workflow.from_yaml(workflow_path)
    else:
        workflow = _get_default_workflow()

    # Open in editor
    yaml_content = workflow.to_yaml()
    edited = editor.edit(contents=yaml_content.encode())

    if edited:
        # Validate and save
        try:
            workflow = Workflow(**__import__("yaml").safe_load(edited))
            workflow.save(workflow_path)
            console.print(f"[green]✓[/green] Saved to {workflow_path}")
        except Exception as e:
            console.print(f"[red]✗[/red] Invalid YAML: {e}")
            raise typer.Exit(1)
    else:
        console.print("[yellow]No changes made.[/yellow]")


@workflow_app.command("init")
def workflow_init(
    scope: Annotated[
        str,
        typer.Option(
            "--scope", "-s",
            help="Scope: 'project' or 'global'.",
        ),
    ] = "project",
    working_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--working-dir", "-w",
            help="Project directory for project-scoped workflow.",
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force", "-f",
            help="Overwrite existing workflow.",
        ),
    ] = False,
):
    """Create a new workflow configuration with defaults."""
    working_dir = (working_dir or Path.cwd()).resolve()

    if scope == "project":
        workflow_path = get_project_config_dir(working_dir) / "workflow.yaml"
    else:
        workflow_path = get_config_dir() / "workflow.yaml"

    if workflow_path.exists() and not force:
        console.print(f"[yellow]Workflow already exists: {workflow_path}[/yellow]")
        console.print("Use --force to overwrite.")
        raise typer.Exit(1)

    workflow = _get_default_workflow()
    workflow.save(workflow_path)
    console.print(f"[green]✓[/green] Created {workflow_path}")


@workflow_app.command("reset")
def workflow_reset(
    scope: Annotated[
        str,
        typer.Option(
            "--scope", "-s",
            help="Scope: 'project' or 'global'.",
        ),
    ] = "project",
    working_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--working-dir", "-w",
            help="Project directory for project-scoped workflow.",
        ),
    ] = None,
):
    """Reset workflow to defaults."""
    working_dir = (working_dir or Path.cwd()).resolve()

    if scope == "project":
        workflow_path = get_project_config_dir(working_dir) / "workflow.yaml"
    else:
        workflow_path = get_config_dir() / "workflow.yaml"

    if not workflow_path.exists():
        console.print(f"[yellow]No workflow found at {workflow_path}[/yellow]")
        raise typer.Exit(1)

    workflow = _get_default_workflow()
    workflow.save(workflow_path)
    console.print(f"[green]✓[/green] Reset {workflow_path} to defaults")


@app.command()
def version():
    """Show version information."""
    console.print(f"[bold cyan]Claudestine[/bold cyan] v{__version__}")
    console.print()
    console.print("[dim]Automated plan implementation orchestrator for Claude Code[/dim]")
    console.print()
    console.print("Default workflow:")
    console.print("  1. /implement_plan - stop for verification")
    console.print("  2. Automated verification (Playwright/uv/docker)")
    console.print("  3. Update plan summary")
    console.print("  4. Git commit + push (conventional, no watermark)")
    console.print("  5. Clear session, repeat")


if __name__ == "__main__":
    app()
