"""Logging for Claudestine workflow execution."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any


class WorkflowLogger:
    """Logs workflow execution to a JSON Lines file."""

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
        safe_name = plan_name.replace("/", "_").replace(" ", "_")
        self.log_path = self.log_dir / f"{timestamp}_{safe_name}.jsonl"

        self._start_time = datetime.now()
        self._write_event("session_start", {
            "plan_name": plan_name,
            "timestamp": self._start_time.isoformat(),
        })

    def log_step_start(self, step_name: str, step_type: str, iteration: int) -> None:
        """Log the start of a workflow step."""
        self._write_event("step_start", {
            "step": step_name,
            "type": step_type,
            "iteration": iteration,
        })

    def log_step_complete(
        self,
        step_name: str,
        success: bool,
        duration_seconds: float,
        output_summary: str | None = None,
    ) -> None:
        """Log the completion of a workflow step."""
        self._write_event("step_complete", {
            "step": step_name,
            "success": success,
            "duration_seconds": round(duration_seconds, 2),
            "output_summary": output_summary[:500] if output_summary else None,
        })

    def log_iteration_complete(self, iteration: int, plan_complete: bool) -> None:
        """Log the completion of a workflow iteration."""
        self._write_event("iteration_complete", {
            "iteration": iteration,
            "plan_complete": plan_complete,
        })

    def log_session_end(self, success: bool, total_iterations: int) -> None:
        """Log the end of the workflow session."""
        duration = (datetime.now() - self._start_time).total_seconds()
        self._write_event("session_end", {
            "success": success,
            "total_iterations": total_iterations,
            "duration_seconds": round(duration, 2),
        })

    def log_error(self, step_name: str, error: str) -> None:
        """Log an error during workflow execution."""
        self._write_event("error", {
            "step": step_name,
            "error": error,
        })

    def log_claude_output(self, step_name: str, output: str) -> None:
        """Log Claude's full output for a step."""
        self._write_event("claude_output", {
            "step": step_name,
            "output": output,
        })

    def _write_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Write an event to the log file."""
        event = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            **data,
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(event) + "\n")

    def get_log_path(self) -> Path:
        """Return the path to the current log file."""
        return self.log_path
