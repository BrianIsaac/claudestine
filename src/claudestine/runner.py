"""Claude CLI runner with real-time streaming output."""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from claudestine.ui.console import StepOutput


@dataclass
class ClaudeResult:
    """Result from a Claude CLI execution."""

    success: bool
    exit_code: int
    output: str
    session_id: str | None = None
    stop_reason: str | None = None
    error: str | None = None


@dataclass
class StreamEvent:
    """Event from streaming output."""

    type: str  # text, tool_use, tool_result, error, done
    content: str
    metadata: dict = field(default_factory=dict)


class ClaudeRunner:
    """Runs Claude CLI with streaming output."""

    def __init__(
        self,
        working_dir: Path,
        allowed_tools: list[str] | None = None,
    ):
        """
        Initialise the runner.

        Args:
            working_dir: Directory to run Claude in.
            allowed_tools: List of tools Claude can use.
        """
        self.working_dir = working_dir
        self.allowed_tools = allowed_tools
        self._session_id: str | None = None

    def run(
        self,
        prompt: str,
        output: StepOutput | None = None,
        on_line: Callable[[str], None] | None = None,
        stop_patterns: list[str] | None = None,
    ) -> ClaudeResult:
        """
        Run Claude CLI with the given prompt.

        Args:
            prompt: The prompt to send to Claude.
            output: StepOutput to stream to.
            on_line: Callback for each line of output.
            stop_patterns: Patterns that indicate we should stop.

        Returns:
            ClaudeResult with execution details.
        """
        cmd = self._build_command(prompt)

        all_output: list[str] = []
        stop_reason: str | None = None

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.working_dir,
                env=self._get_env(),
            )

            if process.stdout is None:
                return ClaudeResult(
                    success=False,
                    exit_code=-1,
                    output="",
                    error="Failed to capture stdout",
                )

            # Stream output using read1() for real-time display
            buffer = ""
            while True:
                chunk = process.stdout.read1(1024)  # type: ignore
                if not chunk:
                    break

                text = chunk.decode("utf-8", errors="replace")
                buffer += text

                # Process complete lines
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    all_output.append(line)

                    # Stream to UI
                    if output:
                        output.append(self._format_line(line))
                    if on_line:
                        on_line(line)

                    # Check for stop patterns
                    if stop_patterns:
                        for pattern in stop_patterns:
                            if re.search(pattern, line, re.IGNORECASE):
                                stop_reason = f"Pattern matched: {pattern}"

                    # Try to extract session ID from JSON output
                    self._try_extract_session_id(line)

            # Process remaining buffer
            if buffer:
                all_output.append(buffer)
                if output:
                    output.append(self._format_line(buffer))

            exit_code = process.wait()

            return ClaudeResult(
                success=exit_code == 0,
                exit_code=exit_code,
                output="\n".join(all_output),
                session_id=self._session_id,
                stop_reason=stop_reason,
            )

        except Exception as e:
            return ClaudeResult(
                success=False,
                exit_code=-1,
                output="\n".join(all_output),
                error=str(e),
            )

    def run_shell(
        self,
        commands: list[str],
        output: StepOutput | None = None,
        skip_if_clean: bool = False,
    ) -> ClaudeResult:
        """
        Run shell commands directly.

        Args:
            commands: List of shell commands to run.
            output: StepOutput to stream to.
            skip_if_clean: Skip if git working tree is clean.

        Returns:
            ClaudeResult with execution details.
        """
        all_output: list[str] = []

        if skip_if_clean:
            # Check if there are changes to commit
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.working_dir,
                capture_output=True,
                text=True,
            )
            if not result.stdout.strip():
                if output:
                    output.append("[dim]No changes to commit[/dim]")
                return ClaudeResult(
                    success=True,
                    exit_code=0,
                    output="No changes to commit",
                    stop_reason="clean",
                )

        for cmd in commands:
            if output:
                output.append(f"[cyan]$ {cmd}[/cyan]")

            try:
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=self.working_dir,
                )

                if process.stdout:
                    for line in process.stdout:
                        decoded = line.decode("utf-8", errors="replace").rstrip()
                        all_output.append(decoded)
                        if output:
                            output.append(decoded)

                exit_code = process.wait()

                if exit_code != 0:
                    return ClaudeResult(
                        success=False,
                        exit_code=exit_code,
                        output="\n".join(all_output),
                        error=f"Command failed: {cmd}",
                    )

            except Exception as e:
                return ClaudeResult(
                    success=False,
                    exit_code=-1,
                    output="\n".join(all_output),
                    error=str(e),
                )

        return ClaudeResult(
            success=True,
            exit_code=0,
            output="\n".join(all_output),
        )

    def clear_session(self) -> None:
        """Clear the current session."""
        self._session_id = None

    def _build_command(self, prompt: str) -> list[str]:
        """Build the Claude CLI command."""
        cmd = ["claude", "-p", prompt]

        if self.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self.allowed_tools)])

        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        return cmd

    def _get_env(self) -> dict:
        """Get environment variables for subprocess."""
        env = os.environ.copy()
        # Ensure Claude outputs to terminal properly
        env["FORCE_COLOR"] = "1"
        return env

    def _format_line(self, line: str) -> str:
        """Format a line for display."""
        # Remove ANSI escape codes for cleaner display
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean = ansi_escape.sub("", line)

        # Highlight key patterns
        if clean.startswith("> "):
            return f"[cyan]{clean}[/cyan]"
        if "error" in clean.lower():
            return f"[red]{clean}[/red]"
        if "success" in clean.lower() or "✓" in clean:
            return f"[green]{clean}[/green]"

        return clean

    def _try_extract_session_id(self, line: str) -> None:
        """Try to extract session ID from output."""
        try:
            data = json.loads(line)
            if "session_id" in data:
                self._session_id = data["session_id"]
        except (json.JSONDecodeError, TypeError):
            pass


def get_git_status(working_dir: Path) -> list[tuple[str, str]]:
    """
    Get list of changed files with their status.

    Args:
        working_dir: Git repository directory.

    Returns:
        List of (status, filepath) tuples.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=working_dir,
            capture_output=True,
            text=True,
        )

        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                status = line[:2].strip() or "?"
                filepath = line[3:]
                files.append((status, filepath))

        return files

    except Exception:
        return []


def generate_commit_message(working_dir: Path) -> str:
    """
    Generate a conventional commit message based on changes.

    Args:
        working_dir: Git repository directory.

    Returns:
        Conventional commit message.
    """
    files = get_git_status(working_dir)

    if not files:
        return "chore: no changes"

    # Analyse changes to determine commit type
    added = [f for s, f in files if s in ("A", "??")]
    modified = [f for s, f in files if s == "M"]
    deleted = [f for s, f in files if s == "D"]

    # Determine primary action
    if added and not modified and not deleted:
        action = "feat"
        desc = "add"
    elif deleted and not added:
        action = "refactor"
        desc = "remove"
    elif modified:
        action = "feat"
        desc = "update"
    else:
        action = "chore"
        desc = "update"

    # Determine scope from file paths
    all_files = [f for _, f in files]
    common_dir = os.path.commonpath(all_files) if all_files else ""

    if common_dir and "/" in common_dir:
        scope = common_dir.split("/")[0]
    elif all_files:
        scope = Path(all_files[0]).stem
    else:
        scope = "misc"

    # Keep it simple and short
    if len(all_files) == 1:
        return f"{action}({scope}): {desc} {Path(all_files[0]).name}"
    else:
        return f"{action}({scope}): {desc} {len(all_files)} files"
