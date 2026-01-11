"""Rich console output with collapsible sections."""

from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from rich.console import Console as RichConsole, Group, RenderableType

if TYPE_CHECKING:
    from claudestine.runner import ClaudeRunner
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
        visible_lines = [line for line in self.lines if line.strip()][-self.MAX_VISIBLE_LINES:]

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
        self._current_phase: int = 0
        self._total_phases: int = 0
        self._runner: "ClaudeRunner | None" = None
        self._paused: bool = False
        self._manual_mode: bool = False

    def set_paused(self, paused: bool) -> None:
        """Set pause state."""
        self._paused = paused
        self.refresh()

    def is_paused(self) -> bool:
        """Check if paused."""
        return self._paused

    def set_manual_mode(self, manual: bool) -> None:
        """Set manual mode state."""
        self._manual_mode = manual
        self.refresh()

    def set_runner(self, runner: "ClaudeRunner") -> None:
        """
        Set the runner for context tracking.

        Args:
            runner: The ClaudeRunner instance.
        """
        self._runner = runner

    def start(self, plan_name: str, total_steps: int) -> None:
        """
        Start the console display.

        Args:
            plan_name: Name of the plan being executed.
            total_steps: Total number of steps per iteration.
        """
        self._plan_name = plan_name
        self._total_steps = total_steps
        self._current_step_num = 0
        self._current_phase = 0
        self._total_phases = 0

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

    def set_total_phases(self, total: int) -> None:
        """Set the total number of phases in the plan."""
        self._total_phases = total
        self.refresh()

    def new_phase(self, phase: int) -> None:
        """
        Start a new phase, resetting step counter and progress.

        Args:
            phase: The phase number starting.
        """
        self._current_phase = phase
        self._current_step_num = 0
        self.steps.clear()

        if self._progress and self._main_task is not None:
            self._progress.reset(self._main_task)

        self.refresh()

    def resume(self) -> None:
        """
        Resume the console display after a pause.

        Unlike start(), this preserves the current step count and phase state.
        Use this when temporarily stopping the display (e.g., for user input).
        """
        if self._live:
            return  # Already running

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
            f"[cyan]{self._plan_name}",
            total=self._total_steps,
            completed=self._current_step_num,
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
        renderables: list[RenderableType] = []

        # Header with phase, step, and context info
        header = Table.grid(expand=True)
        header.add_column()
        header.add_column(justify="right")
        phase_info = f"Phase {self._current_phase}"
        if self._total_phases > 0:
            phase_info += f"/{self._total_phases}"

        # Add context usage if runner is available
        context_info = ""
        if self._runner:
            tokens, window, pct = self._runner.get_context_usage()
            context_info = f"[dim]Context: {tokens // 1000}k/{window // 1000}k ({pct:.1f}%)[/dim] "

        header.add_row(
            "[bold cyan]Claudestine[/bold cyan] [dim]v0.2.0[/dim]",
            f"{context_info}[dim]{phase_info} | Step {self._current_step_num}/{self._total_steps}[/dim]",
        )
        renderables.append(Panel(header, border_style="cyan"))

        # Progress bar
        if self._progress:
            renderables.append(self._progress)

        # Only show the current step (last one in the list)
        if self.steps:
            renderables.append(self.steps[-1].render())

        # Footer with controls hint
        if self._paused:
            if self._manual_mode:
                footer_text = "[yellow]MANUAL MODE[/yellow] - Type your prompt and press Enter"
            else:
                footer_text = "[yellow]PAUSED[/yellow] - Press [bold]C[/bold] to continue, [bold]M[/bold] for manual"
            border_style = "yellow"
        else:
            footer_text = "[dim]Press [bold]P[/bold] to pause, [bold]M[/bold] for manual, Ctrl+C to stop[/dim]"
            border_style = "dim"
        footer = Text.from_markup(footer_text)
        renderables.append(Panel(footer, border_style=border_style))

        return Group(*renderables)

    @contextmanager
    def step(
        self, name: str, *, transient: bool = False
    ) -> Generator[StepOutput, None, None]:
        """
        Context manager for a workflow step.

        Args:
            name: Step name.
            transient: If True, don't increment step counter or progress bar.
                Use for ad-hoc steps like manual prompts that shouldn't count
                towards workflow progress.

        Yields:
            StepOutput instance to collect output.
        """
        if not transient:
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
            # Check if step was interrupted (process killed by user)
            interrupted = self._runner and self._runner.is_interrupted()

            if interrupted and not transient:
                # Rollback counter so retry shows same step number
                self._current_step_num -= 1
                step_output.set_status("interrupted")
            elif interrupted:
                step_output.set_status("interrupted")
            elif self._progress and self._main_task is not None and not transient:
                # Only advance progress on successful completion
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
