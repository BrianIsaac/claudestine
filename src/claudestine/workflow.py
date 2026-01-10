"""Workflow executor for Claudestine."""

import re
import time
from pathlib import Path
from string import Template

from claudestine.config import RunConfig, Step, StepType, Workflow, get_project_config_dir
from claudestine.logging import WorkflowLogger
from claudestine.runner import (
    ClaudeResult,
    ClaudeRunner,
    generate_commit_message,
    get_git_status,
)
from claudestine.ui.console import Console


class WorkflowExecutor:
    """Executes a workflow against a plan."""

    def __init__(
        self,
        workflow: Workflow,
        config: RunConfig,
        console: Console,
    ):
        """
        Initialise the executor.

        Args:
            workflow: Workflow definition to execute.
            config: Run configuration.
            console: Console for output.
        """
        self.workflow = workflow
        self.config = config
        self.console = console
        self.runner = ClaudeRunner(
            working_dir=config.working_dir,
        )

        # Set up logging
        log_dir = get_project_config_dir(config.working_dir)
        self.logger = WorkflowLogger(log_dir, config.plan_path.name)

        # Variables available for template substitution
        self.variables = {
            "plan_path": str(config.plan_path),
            "working_dir": str(config.working_dir),
            **workflow.variables,
        }

    def execute(self) -> bool:
        """
        Execute the full workflow.

        Returns:
            True if workflow completed successfully.
        """
        # Count total phases in plan
        total_phases = self._count_phases()

        self.console.start(
            plan_name=self.config.plan_path.name,
            total_steps=len(self.workflow.steps),
        )
        self.console.set_total_phases(total_phases)

        self.console.info(f"Logging to: {self.logger.get_log_path()}")

        try:
            phase = 0
            max_phases = 50

            while phase < max_phases:
                phase += 1
                self.console.new_phase(phase)

                # Execute each step in sequence
                for step in self.workflow.steps:
                    step_start = time.time()
                    self.logger.log_step_start(step.name, step.type.value, phase)

                    result = self._execute_step(step, phase)

                    step_duration = time.time() - step_start
                    self.logger.log_step_complete(
                        step.name,
                        result.success,
                        step_duration,
                        self._extract_summary(result.output),
                    )

                    if result.output:
                        self.logger.log_claude_output(step.name, self._format_output_for_log(result.output))

                    if not result.success:
                        if step.require_success:
                            self.logger.log_error(step.name, result.error or "Step failed")
                            self.console.error(
                                f"Step '{step.name}' failed and requires success"
                            )
                            self.logger.log_session_end(False, phase)
                            return False

                # Check plan progress after each full phase
                plan_complete = self._is_plan_complete()
                self.logger.log_phase_complete(phase, plan_complete)

                if plan_complete:
                    self.console.success("Plan fully implemented!")
                    self.logger.log_session_end(True, phase)
                    return True

            self.console.warning(f"Reached max phases ({max_phases})")
            self.logger.log_session_end(False, phase)
            return False

        finally:
            self.console.stop()

    def _count_phases(self) -> int:
        """Count the number of phases in the plan file."""
        try:
            content = self.config.plan_path.read_text()
            # Count "## Phase X" headers
            return len(re.findall(r"^##\s+Phase\s+\d+", content, re.MULTILINE | re.IGNORECASE))
        except Exception:
            return 0

    def _extract_summary(self, output: str) -> str | None:
        """Extract a human-readable summary from Claude output."""
        if not output:
            return None

        # Try to extract just text content from stream-json
        lines = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            try:
                import json
                data = json.loads(line)
                if data.get("type") == "assistant":
                    message = data.get("message", {})
                    for item in message.get("content", []):
                        if item.get("type") == "text":
                            text = item.get("text", "").strip()
                            if text:
                                lines.append(text)
            except (json.JSONDecodeError, TypeError):
                pass

        if lines:
            return "\n".join(lines)[:500]
        return output[:500] if output else None

    def _format_output_for_log(self, output: str) -> str:
        """Format Claude output for readable log."""
        if not output:
            return ""

        lines = []
        for line in output.split("\n"):
            if not line.strip():
                continue
            try:
                import json
                data = json.loads(line)

                if data.get("type") == "assistant":
                    message = data.get("message", {})
                    for item in message.get("content", []):
                        if item.get("type") == "text":
                            text = item.get("text", "").strip()
                            if text:
                                lines.append(text)
                        elif item.get("type") == "tool_use":
                            tool = item.get("name", "unknown")
                            lines.append(f"[Tool: {tool}]")

                elif data.get("type") == "result":
                    result = data.get("result", "")
                    if result:
                        lines.append(f"\n--- Result ---\n{result}")

            except (json.JSONDecodeError, TypeError):
                # Not JSON, include as-is if it looks meaningful
                clean = line.strip()
                if clean and not clean.startswith("{"):
                    lines.append(clean)

        return "\n".join(lines) if lines else output

    def execute_dry_run(self) -> None:
        """Show what would be executed without running."""
        self.console.show_workflow(
            self.workflow.name,
            [step.name for step in self.workflow.steps],
        )

        self.console.rule("Steps")

        for i, step in enumerate(self.workflow.steps, 1):
            self.console.print(f"\n[bold]{i}. {step.name}[/bold] [{step.type.value}]")

            if step.prompt:
                prompt = self._substitute_variables(step.prompt)
                self.console.print(f"   [dim]Prompt:[/dim]")
                for line in prompt.strip().split("\n")[:5]:
                    self.console.print(f"   [cyan]{line}[/cyan]")
                if prompt.count("\n") > 5:
                    self.console.print(f"   [dim]... ({prompt.count(chr(10)) - 5} more lines)[/dim]")

            if step.commands:
                self.console.print(f"   [dim]Commands:[/dim]")
                for cmd in step.commands:
                    self.console.print(f"   [cyan]$ {cmd}[/cyan]")

            if step.stop_on:
                self.console.print(f"   [dim]Stop on:[/dim] {', '.join(step.stop_on)}")

    def _execute_step(self, step: Step, iteration: int = 1) -> ClaudeResult:
        """
        Execute a single workflow step.

        Args:
            step: Step to execute.
            iteration: Current workflow iteration number.

        Returns:
            Result of the step execution.
        """
        with self.console.step(step.name) as output:
            if step.type == StepType.CLAUDE:
                return self._execute_claude_step(step, output)
            elif step.type == StepType.SHELL:
                return self._execute_shell_step(step, output)
            elif step.type == StepType.INTERNAL:
                return self._execute_internal_step(step, output)
            else:
                output.append(f"[red]Unknown step type: {step.type}[/red]")
                return ClaudeResult(
                    success=False,
                    exit_code=1,
                    output="",
                    error=f"Unknown step type: {step.type}",
                )

    def _execute_claude_step(self, step: Step, output) -> ClaudeResult:
        """Execute a Claude prompt step."""
        if not step.prompt:
            output.append("[red]No prompt specified[/red]")
            return ClaudeResult(
                success=False,
                exit_code=1,
                output="",
                error="No prompt specified",
            )

        prompt = self._substitute_variables(step.prompt)

        # Set allowed tools if specified
        if step.allowed_tools:
            self.runner.allowed_tools = step.allowed_tools

        result = self.runner.run(
            prompt=prompt,
            output=output if step.stream else None,
            stop_patterns=step.stop_on,
        )

        return result

    def _execute_shell_step(self, step: Step, output) -> ClaudeResult:
        """Execute shell commands step."""
        if not step.commands:
            output.append("[red]No commands specified[/red]")
            return ClaudeResult(
                success=False,
                exit_code=1,
                output="",
                error="No commands specified",
            )

        # Substitute variables in commands
        commands = [self._substitute_variables(cmd) for cmd in step.commands]

        # Handle commit message generation
        commands = [
            cmd.replace("{commit_message}", generate_commit_message(self.config.working_dir))
            for cmd in commands
        ]

        # Handle auto_push flag
        if not self.config.auto_push:
            commands = [cmd for cmd in commands if "git push" not in cmd]

        return self.runner.run_shell(
            commands=commands,
            output=output,
            skip_if_clean=step.skip_if_clean,
        )

    def _execute_internal_step(self, step: Step, output) -> ClaudeResult:
        """Execute internal action step."""
        if step.action == "clear_session":
            self.runner.clear_session()
            output.append("[dim]Session cleared[/dim]")
            return ClaudeResult(success=True, exit_code=0, output="Session cleared")

        elif step.action == "show_changes":
            files = get_git_status(self.config.working_dir)
            if files:
                self.console.show_files_changed(files)
            else:
                output.append("[dim]No changes[/dim]")
            return ClaudeResult(success=True, exit_code=0, output="")

        else:
            output.append(f"[red]Unknown action: {step.action}[/red]")
            return ClaudeResult(
                success=False,
                exit_code=1,
                output="",
                error=f"Unknown action: {step.action}",
            )

    def _substitute_variables(self, text: str) -> str:
        """Substitute variables in text."""
        # Use safe_substitute to avoid KeyError on missing variables
        template = Template(text)
        # First try ${var} style
        result = template.safe_substitute(self.variables)
        # Then try {var} style (for backwards compatibility)
        for key, value in self.variables.items():
            result = result.replace(f"{{{key}}}", str(value))
        return result

    def _is_plan_complete(self) -> bool:
        """Check if the plan file indicates completion."""
        try:
            content = self.config.plan_path.read_text()
            # Check for 100% progress or all phases complete
            if "100%" in content:
                return True
            # Count completed vs total phases
            completed = len(re.findall(r"\*\*Status:\*\*\s*complete", content, re.I))
            total = len(re.findall(r"##\s+Phase\s+\d+", content, re.I))
            if total > 0 and completed >= total:
                return True
        except Exception:
            pass

        return False
