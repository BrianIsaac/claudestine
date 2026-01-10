"""Textual TUI for Claudestine orchestrator."""

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Footer, Header, Label, ProgressBar, RichLog, Static
from textual.reactive import reactive
from textual.worker import Worker, get_current_worker

from claudestine.models import OrchestratorState, Phase, StepStatus


class PhaseList(Static):
    """Widget displaying the list of phases and their statuses."""

    def __init__(self, phases: list[Phase] | None = None, **kwargs):
        """Initialise the phase list."""
        super().__init__(**kwargs)
        self.phases = phases or []
        self.current_index = 0

    def update_phases(self, phases: list[Phase], current_index: int) -> None:
        """Update the displayed phases."""
        self.phases = phases
        self.current_index = current_index
        self.refresh()

    def render(self) -> str:
        """Render the phase list."""
        if not self.phases:
            return "[dim]No phases loaded[/dim]"

        lines = ["[bold]Phases[/bold]", ""]
        for i, phase in enumerate(self.phases):
            status_icon = self._get_status_icon(phase.status)
            is_current = i == self.current_index

            if is_current:
                lines.append(f"[bold cyan]> {status_icon} {phase.name}[/bold cyan]")
            else:
                lines.append(f"  {status_icon} {phase.name}")

        return "\n".join(lines)

    def _get_status_icon(self, status: StepStatus) -> str:
        """Get the icon for a status."""
        icons = {
            StepStatus.PENDING: "[dim]○[/dim]",
            StepStatus.IN_PROGRESS: "[yellow]●[/yellow]",
            StepStatus.COMPLETED: "[green]✓[/green]",
            StepStatus.FAILED: "[red]✗[/red]",
            StepStatus.SKIPPED: "[dim]⊘[/dim]",
        }
        return icons.get(status, "○")


class StatusDisplay(Static):
    """Widget displaying orchestration status."""

    status = reactive("READY")
    iteration = reactive(0)
    progress = reactive(0.0)

    def render(self) -> str:
        """Render the status display."""
        status_colours = {
            "READY": "blue",
            "RUNNING": "yellow",
            "VERIFYING": "cyan",
            "COMMITTING": "magenta",
            "PAUSED": "yellow",
            "STOPPED": "red",
            "COMPLETE": "green",
            "FAILED": "red",
        }
        colour = status_colours.get(self.status, "white")

        progress_pct = int(self.progress)
        bar_filled = int(self.progress / 5)
        bar_empty = 20 - bar_filled
        bar = f"[green]{'█' * bar_filled}[/green][dim]{'░' * bar_empty}[/dim]"

        return (
            f"[bold]Status:[/bold] [{colour}]{self.status}[/{colour}]\n"
            f"[bold]Iteration:[/bold] {self.iteration}\n"
            f"[bold]Progress:[/bold] {bar} {progress_pct}%"
        )


class OutputLog(RichLog):
    """Widget for displaying live output."""

    def __init__(self, **kwargs):
        """Initialise the output log."""
        super().__init__(highlight=True, markup=True, wrap=True, **kwargs)


class ClaudestineApp(App):
    """Main Claudestine TUI application."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 2;
        grid-columns: 1fr 2fr;
        grid-rows: auto 1fr auto;
    }

    Header {
        column-span: 2;
    }

    #plan-info {
        height: 3;
        column-span: 2;
        padding: 0 1;
        background: $surface;
    }

    #phase-container {
        height: 100%;
        padding: 1;
        border: round $primary;
    }

    #output-container {
        height: 100%;
        padding: 1;
        border: round $secondary;
    }

    #status-bar {
        height: 5;
        column-span: 2;
        padding: 0 1;
        background: $surface;
    }

    Footer {
        column-span: 2;
    }

    PhaseList {
        height: 100%;
    }

    OutputLog {
        height: 100%;
    }

    ProgressBar {
        width: 100%;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("p", "pause", "Pause"),
        Binding("s", "stop", "Stop"),
        Binding("c", "clear_log", "Clear"),
    ]

    TITLE = "Claudestine"
    SUB_TITLE = "Plan Implementation Orchestrator"

    def __init__(self, state: OrchestratorState | None = None, **kwargs):
        """Initialise the app."""
        super().__init__(**kwargs)
        self.state = state
        self._orchestrator = None
        self._worker: Worker | None = None
        self._paused = False

        # Widget references
        self._phase_list: PhaseList | None = None
        self._output_log: OutputLog | None = None
        self._status_display: StatusDisplay | None = None
        self._progress_bar: ProgressBar | None = None
        self._plan_label: Label | None = None

    def set_orchestrator(self, orchestrator) -> None:
        """Set the orchestrator instance."""
        self._orchestrator = orchestrator

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Header()

        yield Container(
            Label("Plan: (none loaded)", id="plan-label"),
            ProgressBar(total=100, show_eta=False, id="progress"),
            id="plan-info",
        )

        yield Container(
            PhaseList(id="phase-list"),
            id="phase-container",
        )

        yield Container(
            OutputLog(id="output-log"),
            id="output-container",
        )

        yield Container(
            StatusDisplay(id="status-display"),
            id="status-bar",
        )

        yield Footer()

    def on_mount(self) -> None:
        """Initialise widgets and start orchestration."""
        self._phase_list = self.query_one("#phase-list", PhaseList)
        self._output_log = self.query_one("#output-log", OutputLog)
        self._status_display = self.query_one("#status-display", StatusDisplay)
        self._progress_bar = self.query_one("#progress", ProgressBar)
        self._plan_label = self.query_one("#plan-label", Label)

        if self.state:
            self.update_state(self.state)

        # Start orchestration in background worker
        if self._orchestrator:
            self._worker = self.run_worker(
                self._run_orchestration,
                name="orchestrator",
                exclusive=True,
            )

    async def _run_orchestration(self) -> bool:
        """Run the orchestration loop in a worker."""
        if not self._orchestrator:
            return False

        try:
            result = await self._orchestrator.run()
            if result:
                self.call_from_thread(self._on_complete)
            else:
                self.call_from_thread(self._on_failed)
            return result
        except Exception as e:
            self.call_from_thread(self.log_error, f"Orchestration error: {e}")
            self.call_from_thread(self._on_failed)
            return False

    def _on_complete(self) -> None:
        """Handle orchestration completion."""
        if self._status_display:
            self._status_display.status = "COMPLETE"
        self.log_success("Plan implementation complete!")

    def _on_failed(self) -> None:
        """Handle orchestration failure."""
        if self._status_display:
            self._status_display.status = "FAILED"

    def update_state(self, state: OrchestratorState) -> None:
        """Update the UI with new state."""
        self.state = state

        if self._plan_label:
            self._plan_label.update(f"Plan: {state.plan.title}")

        if self._phase_list:
            self._phase_list.update_phases(
                state.plan.phases, state.plan.current_phase_index
            )

        if self._progress_bar:
            self._progress_bar.update(progress=state.plan.progress_percentage)

        if self._status_display:
            self._status_display.progress = state.plan.progress_percentage

    def update_phase(self, phase_name: str, status: str) -> None:
        """Update current phase display."""
        if self._status_display:
            self._status_display.status = status
        self.log_info(f"Phase: {phase_name} - {status}")

    def log_output(self, message: str) -> None:
        """Add a message to the output log."""
        if self._output_log:
            self._output_log.write(message)

    def log_info(self, message: str) -> None:
        """Log an info message."""
        self.log_output(f"[blue]>[/blue] {message}")

    def log_success(self, message: str) -> None:
        """Log a success message."""
        self.log_output(f"[green]✓[/green] {message}")

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        self.log_output(f"[yellow]![/yellow] {message}")

    def log_error(self, message: str) -> None:
        """Log an error message."""
        self.log_output(f"[red]✗[/red] {message}")

    def action_quit(self) -> None:
        """Handle quit action."""
        if self._orchestrator:
            self._orchestrator.stop("User quit")
        self.exit()

    def action_pause(self) -> None:
        """Handle pause action."""
        self._paused = not self._paused
        if self._status_display:
            if self._paused:
                self._status_display.status = "PAUSED"
                self.log_warning("Paused - press 'p' to resume")
            else:
                self._status_display.status = "RUNNING"
                self.log_info("Resumed")

    def action_stop(self) -> None:
        """Handle stop action."""
        if self._orchestrator:
            self._orchestrator.stop("User stopped")
        if self._status_display:
            self._status_display.status = "STOPPED"
        self.log_warning("Stopped by user")

    def action_clear_log(self) -> None:
        """Clear the output log."""
        if self._output_log:
            self._output_log.clear()
