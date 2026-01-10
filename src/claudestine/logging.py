"""Logging for Claudestine workflow execution."""

from datetime import datetime
from pathlib import Path


class WorkflowLogger:
    """Logs workflow execution to a readable markdown file."""

    def __init__(self, log_dir: Path, plan_name: str):
        """
        Initialise the logger.

        Args:
            log_dir: Directory to store log files.
            plan_name: Name of the plan being executed.
        """
        self.log_dir = log_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = plan_name.replace("/", "_").replace(" ", "_").replace(".md", "")
        self.log_path = self.log_dir / f"{timestamp}_{safe_name}.md"

        self._start_time = datetime.now()
        self._current_iteration = 0

        self._write(f"# Claudestine Execution Log\n\n")
        self._write(f"**Plan:** {plan_name}\n")
        self._write(f"**Started:** {self._start_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        self._write("---\n\n")

    def log_step_start(self, step_name: str, step_type: str, iteration: int) -> None:
        """Log the start of a workflow step."""
        if iteration != self._current_iteration:
            self._current_iteration = iteration
            self._write(f"## Iteration {iteration}\n\n")

        self._write(f"### {step_name} ({step_type})\n\n")
        self._write(f"*Started: {datetime.now().strftime('%H:%M:%S')}*\n\n")

    def log_step_complete(
        self,
        step_name: str,
        success: bool,
        duration_seconds: float,
        output_summary: str | None = None,
    ) -> None:
        """Log the completion of a workflow step."""
        status = "SUCCESS" if success else "FAILED"
        self._write(f"**Status:** {status} ({duration_seconds:.1f}s)\n\n")

        if output_summary:
            self._write("<details>\n<summary>Output Summary</summary>\n\n```\n")
            self._write(output_summary[:500])
            if len(output_summary) > 500:
                self._write("\n... (truncated)")
            self._write("\n```\n</details>\n\n")

    def log_iteration_complete(self, iteration: int, plan_complete: bool) -> None:
        """Log the completion of a workflow iteration."""
        if plan_complete:
            self._write(f"**Iteration {iteration} Result:** Plan complete\n\n")
        else:
            self._write(f"**Iteration {iteration} Result:** Continuing to next iteration\n\n")
        self._write("---\n\n")

    def log_session_end(self, success: bool, total_iterations: int) -> None:
        """Log the end of the workflow session."""
        duration = (datetime.now() - self._start_time).total_seconds()
        status = "SUCCESS" if success else "FAILED"

        self._write("## Summary\n\n")
        self._write(f"- **Status:** {status}\n")
        self._write(f"- **Total Iterations:** {total_iterations}\n")
        self._write(f"- **Duration:** {duration:.1f}s\n")
        self._write(f"- **Ended:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    def log_error(self, step_name: str, error: str) -> None:
        """Log an error during workflow execution."""
        self._write(f"**ERROR in {step_name}:**\n\n```\n{error}\n```\n\n")

    def log_claude_output(self, step_name: str, output: str) -> None:
        """Log Claude's full output for a step."""
        self._write("<details>\n<summary>Full Claude Output</summary>\n\n```\n")
        self._write(output)
        self._write("\n```\n</details>\n\n")

    def _write(self, text: str) -> None:
        """Append text to the log file."""
        with open(self.log_path, "a") as f:
            f.write(text)

    def get_log_path(self) -> Path:
        """Return the path to the current log file."""
        return self.log_path
