"""Rich console output with collapsible sections."""

from contextlib import contextmanager
from typing import Generator

from rich.console import Console as RichConsole
from rich.console import Group
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree


class StepOutput:
    """Collapsible output collector for a step."""

    def __init__(self, name: str, console: "Console"):
        """
        Initialise step output.

        Args:
            name: Step name.
            console: Parent console instance.
        """
        self.name = name
        self.console = console
        self.lines: list[str] = []
        self.collapsed = False
        self.status = "running"  # running, success, failed, skipped

    def append(self, line: str) -> None:
        """Add a line of output."""
        self.lines.append(line)
        if not self.collapsed:
            self.console.refresh()

    def set_status(self, status: str) -> None:
        """Set the step status."""
        self.status = status
        self.console.refresh()

    def collapse(self) -> None:
        """Collapse the output."""
        self.collapsed = True
        self.console.refresh()

    def expand(self) -> None:
        """Expand the output."""
        self.collapsed = False
        self.console.refresh()

    MAX_VISIBLE_LINES = 15  # Fixed height output area

    def render(self) -> Panel:
        """Render the step output as a Rich Panel."""
        status_styles = {
            "running": ("yellow", "●"),
            "success": ("green", "✓"),
            "failed": ("red", "✗"),
            "skipped": ("dim", "⊘"),
        }
        colour, icon = status_styles.get(self.status, ("white", "?"))

        title = f"[{colour}]{icon}[/{colour}] {self.name}"

        if self.collapsed:
            line_count = len(self.lines)
            return Panel(
                Text(f"[{line_count} lines]", style="dim"),
                title=title,
                title_align="left",
                border_style="dim",
                height=3,
            )

        # Fixed height: show last N lines only
        visible_lines = [l for l in self.lines if l.strip()][-self.MAX_VISIBLE_LINES:]

        if visible_lines:
            if len(self.lines) > self.MAX_VISIBLE_LINES:
                header = f"[dim]... ({len(self.lines) - self.MAX_VISIBLE_LINES} more above)[/dim]\n"
                content = Text.from_markup(header + "\n".join(visible_lines))
            else:
                content = Text.from_markup("\n".join(visible_lines))
        else:
            content = Text("(waiting...)", style="dim")

        return Panel(
            content,
            title=title,
            title_align="left",
            border_style=colour,
            height=self.MAX_VISIBLE_LINES + 4,  # Fixed height
        )


class Console:
    """Rich console with collapsible step outputs."""

    def __init__(self, verbose: bool = False):
        """
        Initialise the console.

        Args:
            verbose: Show verbose output.
        """
        self.console = RichConsole()
        self.verbose = verbose
        self.steps: list[StepOutput] = []
        self.current_step: StepOutput | None = None
        self._live: Live | None = None
        self._progress: Progress | None = None
        self._main_task: TaskID | None = None
        self._step_task: TaskID | None = None
        self._plan_name: str = ""
        self._total_steps: int = 0
        self._current_step_num: int = 0

    def start(self, plan_name: str, total_steps: int) -> None:
        """
        Start the console display.

        Args:
            plan_name: Name of the plan being executed.
            total_steps: Total number of steps.
        """
        self._plan_name = plan_name
        self._total_steps = total_steps
        self._current_step_num = 0

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
            expand=True,
        )

        self._main_task = self._progress.add_task(
            f"[cyan]{plan_name}",
            total=total_steps,
        )

        self._live = Live(
            self._render(),
            console=self.console,
            refresh_per_second=4,
            transient=False,
        )
        self._live.start()

    def stop(self) -> None:
        """Stop the console display."""
        if self._live:
            self._live.stop()
            self._live = None

    def refresh(self) -> None:
        """Refresh the display."""
        if self._live:
            self._live.update(self._render())

    def _render(self) -> Group:
        """Render the full display."""
        renderables = []

        # Header
        header = Table.grid(expand=True)
        header.add_column()
        header.add_column(justify="right")
        header.add_row(
            f"[bold cyan]Claudestine[/bold cyan] [dim]v0.2.0[/dim]",
            f"[dim]Step {self._current_step_num}/{self._total_steps}[/dim]",
        )
        renderables.append(Panel(header, border_style="cyan"))

        # Progress bar
        if self._progress:
            renderables.append(self._progress)

        # Step outputs (collapsed old ones, expanded current one)
        for i, step in enumerate(self.steps):
            # Auto-collapse completed steps except the last few
            if i < len(self.steps) - 2 and step.status in ("success", "skipped"):
                step.collapsed = True
            renderables.append(step.render())

        # Footer with hint
        footer = Text("Press Ctrl+C to stop", style="dim")
        renderables.append(Panel(footer, border_style="dim"))

        return Group(*renderables)

    @contextmanager
    def step(self, name: str) -> Generator[StepOutput, None, None]:
        """
        Context manager for a workflow step.

        Args:
            name: Step name.

        Yields:
            StepOutput instance to collect output.
        """
        self._current_step_num += 1

        step_output = StepOutput(name, self)
        self.steps.append(step_output)
        self.current_step = step_output

        if self._progress and self._main_task is not None:
            self._progress.update(
                self._main_task,
                description=f"[cyan]{name}",
            )

        self.refresh()

        try:
            yield step_output
            if step_output.status == "running":
                step_output.set_status("success")
        except Exception:
            step_output.set_status("failed")
            raise
        finally:
            if self._progress and self._main_task is not None:
                self._progress.advance(self._main_task)
            self.current_step = None

    def print(self, message: str, style: str | None = None) -> None:
        """Print a message (outside of steps)."""
        if self._live:
            self._live.console.print(message, style=style)
        else:
            self.console.print(message, style=style)

    def info(self, message: str) -> None:
        """Print an info message."""
        self.print(f"[blue]>[/blue] {message}")

    def success(self, message: str) -> None:
        """Print a success message."""
        self.print(f"[green]✓[/green] {message}")

    def warning(self, message: str) -> None:
        """Print a warning message."""
        self.print(f"[yellow]![/yellow] {message}")

    def error(self, message: str) -> None:
        """Print an error message."""
        self.print(f"[red]✗[/red] {message}")

    def rule(self, title: str = "") -> None:
        """Print a horizontal rule."""
        self.console.print(Rule(title))

    def show_workflow(self, workflow_name: str, steps: list[str]) -> None:
        """Display the workflow overview."""
        tree = Tree(f"[bold cyan]{workflow_name}[/bold cyan]")
        for i, step in enumerate(steps, 1):
            tree.add(f"[dim]{i}.[/dim] {step}")
        self.console.print(tree)
        self.console.print()

    def show_files_changed(self, files: list[tuple[str, str]]) -> None:
        """
        Show files that were changed.

        Args:
            files: List of (status, filepath) tuples.
        """
        if not files:
            return

        table = Table(title="Files Changed", expand=True)
        table.add_column("Status", style="bold", width=8)
        table.add_column("File")

        status_styles = {
            "A": "green",   # Added
            "M": "yellow",  # Modified
            "D": "red",     # Deleted
            "?": "cyan",    # Untracked
        }

        for status, filepath in files:
            style = status_styles.get(status, "white")
            table.add_row(f"[{style}]{status}[/{style}]", filepath)

        self.console.print(table)
