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

        if output:
            output.append(f"[dim]$ {' '.join(cmd[:3])}...[/dim]")

        all_output: list[str] = []
        stop_reason: str | None = None

        try:
            # Use unbuffered output for real-time streaming
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=self.working_dir,
                env=self._get_env(),
                bufsize=0,  # Unbuffered
            )

            if process.stdout is None:
                return ClaudeResult(
                    success=False,
                    exit_code=-1,
                    output="",
                    error="Failed to capture stdout",
                )

            # Read line by line for streaming
            for line_bytes in iter(process.stdout.readline, b""):
                line = line_bytes.decode("utf-8", errors="replace").rstrip()

                if not line:
                    continue

                all_output.append(line)

                # Format and display
                formatted = self._format_line(line)
                if output:
                    output.append(formatted)
                if on_line:
                    on_line(line)

                # Check for stop patterns
                if stop_patterns:
                    for pattern in stop_patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            stop_reason = f"Pattern matched: {pattern}"

                # Try to extract session ID from JSON output
                self._try_extract_session_id(line)

            exit_code = process.wait()

            return ClaudeResult(
                success=exit_code == 0,
                exit_code=exit_code,
                output="\n".join(all_output),
                session_id=self._session_id,
                stop_reason=stop_reason,
            )

        except Exception as e:
            error_msg = str(e)
            if output:
                output.append(f"[red]Error: {error_msg}[/red]")
            return ClaudeResult(
                success=False,
                exit_code=-1,
                output="\n".join(all_output),
                error=error_msg,
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
                    bufsize=0,
                )

                if process.stdout:
                    for line_bytes in iter(process.stdout.readline, b""):
                        line = line_bytes.decode("utf-8", errors="replace").rstrip()
                        if line:
                            all_output.append(line)
                            if output:
                                output.append(line)

                exit_code = process.wait()

                if exit_code != 0:
                    if output:
                        output.append(f"[red]Command failed with exit code {exit_code}[/red]")
                    return ClaudeResult(
                        success=False,
                        exit_code=exit_code,
                        output="\n".join(all_output),
                        error=f"Command failed: {cmd}",
                    )

            except Exception as e:
                if output:
                    output.append(f"[red]Error: {e}[/red]")
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

    def _build_command(self, prompt: str, streaming: bool = True) -> list[str]:
        """Build the Claude CLI command."""
        cmd = ["claude", "-p", prompt]

        # Allow Claude to execute tools without confirmation
        cmd.append("--dangerously-skip-permissions")

        # Use stream-json for real-time output
        if streaming:
            cmd.extend(["--output-format", "stream-json", "--verbose"])

        if self.allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self.allowed_tools)])

        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        return cmd

    def _get_env(self) -> dict:
        """Get environment variables for subprocess."""
        env = os.environ.copy()
        # Disable colours in Claude output for cleaner parsing
        env["NO_COLOR"] = "1"
        # Force line buffering
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _format_line(self, line: str) -> str:
        """Format a stream-json line for display."""
        if not line.strip():
            return ""

        # Try to parse as JSON (stream-json format)
        try:
            data = json.loads(line)
            return self._format_stream_event(data)
        except json.JSONDecodeError:
            pass

        # Fallback: plain text formatting
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        clean = ansi_escape.sub("", line)

        if not clean.strip():
            return ""

        if clean.startswith("> "):
            return f"[cyan]{clean}[/cyan]"
        if "error" in clean.lower():
            return f"[red]{clean}[/red]"
        if "success" in clean.lower() or "✓" in clean:
            return f"[green]{clean}[/green]"

        return clean

    def _format_stream_event(self, data: dict) -> str:
        """Format a stream-json event for display."""
        event_type = data.get("type", "")

        if event_type == "system" and data.get("subtype") == "init":
            session_id = data.get("session_id", "")
            self._session_id = session_id
            return f"[dim]Session: {session_id[:8]}...[/dim]"

        if event_type == "assistant":
            message = data.get("message", {})
            content = message.get("content", [])

            lines = []
            for item in content:
                if item.get("type") == "text":
                    text = item.get("text", "")
                    if text:
                        lines.append(text)
                elif item.get("type") == "tool_use":
                    tool = item.get("name", "unknown")
                    lines.append(f"[cyan]> Using tool: {tool}[/cyan]")

            return "\n".join(lines) if lines else ""

        if event_type == "tool_result":
            return "[dim]> Tool completed[/dim]"

        if event_type == "result":
            result = data.get("result", "")
            if result:
                # Don't repeat the full result, just show summary
                cost = data.get("total_cost_usd", 0)
                return f"[green]Done[/green] [dim](${cost:.4f})[/dim]"

        # Skip other event types
        return ""

    def _try_extract_session_id(self, line: str) -> None:
        """Try to extract session ID from output."""
        # Look for session_id in JSON
        if "session_id" in line:
            try:
                data = json.loads(line)
                if "session_id" in data:
                    self._session_id = data["session_id"]
            except (json.JSONDecodeError, TypeError):
                # Try regex fallback
                match = re.search(r'"session_id":\s*"([^"]+)"', line)
                if match:
                    self._session_id = match.group(1)


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

    added = [f for s, f in files if s in ("A", "??")]
    modified = [f for s, f in files if s == "M"]
    deleted = [f for s, f in files if s == "D"]

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

    all_files = [f for _, f in files]
    common_dir = os.path.commonpath(all_files) if all_files else ""

    if common_dir and "/" in common_dir:
        scope = common_dir.split("/")[0]
    elif all_files:
        scope = Path(all_files[0]).stem
    else:
        scope = "misc"

    if len(all_files) == 1:
        return f"{action}({scope}): {desc} {Path(all_files[0]).name}"
    else:
        return f"{action}({scope}): {desc} {len(all_files)} files"
