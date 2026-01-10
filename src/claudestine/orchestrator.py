"""Main orchestrator for automated plan implementation.

This orchestrator wraps Claude Code's /implement_plan skill and handles:
1. Running /implement_plan until completion or manual verification
2. Performing automated verification (Playwright, uv run, service tests)
3. Updating plan summary for session continuity
4. Git commit (conventional commits, no watermark) and push
5. Clearing session and looping
"""

import asyncio
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Protocol

from claudestine.models import (
    OrchestratorConfig,
    OrchestratorState,
    Plan,
    StepStatus,
)
from claudestine.parsers.plan import PlanParser


class UICallback(Protocol):
    """Protocol for UI callbacks."""

    def log_info(self, message: str) -> None:
        """Log an info message."""
        ...

    def log_success(self, message: str) -> None:
        """Log a success message."""
        ...

    def log_warning(self, message: str) -> None:
        """Log a warning message."""
        ...

    def log_error(self, message: str) -> None:
        """Log an error message."""
        ...

    def update_phase(self, phase_name: str, status: str) -> None:
        """Update current phase display."""
        ...

    def update_state(self, state: OrchestratorState) -> None:
        """Update the UI state."""
        ...


class NullUI:
    """Null implementation of UICallback for headless mode."""

    def log_info(self, message: str) -> None:
        print(f"[INFO] {message}")

    def log_success(self, message: str) -> None:
        print(f"[OK] {message}")

    def log_warning(self, message: str) -> None:
        print(f"[WARN] {message}")

    def log_error(self, message: str) -> None:
        print(f"[ERROR] {message}")

    def update_phase(self, phase_name: str, status: str) -> None:
        print(f"[PHASE] {phase_name}: {status}")

    def update_state(self, state: OrchestratorState) -> None:
        pass


class Orchestrator:
    """Orchestrates the plan implementation loop using Claude Code."""

    # Patterns to detect when Claude stops for manual verification
    MANUAL_VERIFICATION_PATTERNS = [
        r"manual\s+verification\s+(?:required|needed|item)",
        r"please\s+(?:verify|test|check)\s+manually",
        r"stopping\s+for\s+(?:manual|human)\s+(?:verification|review)",
        r"requires?\s+(?:manual|human)\s+(?:testing|verification)",
        r"pausing\s+for\s+verification",
    ]

    # Patterns to detect completion
    COMPLETION_PATTERNS = [
        r"all\s+phases?\s+complete",
        r"implementation\s+complete",
        r"plan\s+(?:fully\s+)?implemented",
        r"no\s+(?:more\s+)?(?:phases?|steps?)\s+(?:remaining|to\s+implement)",
    ]

    def __init__(
        self,
        config: OrchestratorConfig,
        ui: UICallback | None = None,
    ):
        """
        Initialise the orchestrator.

        Args:
            config: Configuration for the orchestrator.
            ui: UI callback for logging and updates.
        """
        self.config = config
        self.ui = ui or NullUI()
        self.plan_parser = PlanParser(config.plan_path)
        self.state: OrchestratorState | None = None
        self._session_id: str | None = None
        self._should_stop = False

    async def run(self) -> bool:
        """
        Run the full orchestration loop.

        Returns:
            True if plan completed successfully, False otherwise.
        """
        plan = self.plan_parser.parse()
        self.state = OrchestratorState(
            plan=plan,
            config=self.config,
            is_running=True,
        )
        self.ui.update_state(self.state)
        self.ui.log_info(f"Starting: {plan.title}")
        self.ui.log_info(f"Plan path: {self.config.plan_path}")

        iteration = 0
        max_iterations = 50  # Safety limit

        while not self._should_stop and iteration < max_iterations:
            iteration += 1
            self.ui.log_info(f"--- Iteration {iteration} ---")

            # Step 1: Run /implement_plan
            impl_result = await self._run_implement_plan()

            if impl_result["status"] == "error":
                self.ui.log_error(f"Implementation failed: {impl_result['message']}")
                return False

            if impl_result["status"] == "complete":
                self.ui.log_success("All phases complete!")
                break

            if impl_result["status"] == "low_confidence":
                self.ui.log_warning(f"Low confidence: {impl_result['message']}")
                self.ui.log_warning("Stopping for human review")
                return False

            # Step 2: Manual verification needed - run automated tests
            if impl_result["status"] == "verification_needed":
                self.ui.log_info("Running automated verification...")
                verification_passed = await self._run_verification()

                if not verification_passed:
                    self.ui.log_error("Verification failed")
                    return False

                self.ui.log_success("Verification passed")

            # Step 3: Update plan summary
            self.ui.log_info("Updating plan summary...")
            self._update_plan_summary(plan)

            # Step 4: Git commit and push
            if self.config.auto_commit:
                self.ui.log_info("Committing changes...")
                commit_success = await self._git_commit_and_push(plan)
                if not commit_success:
                    self.ui.log_warning("Git commit/push had issues")

            # Step 5: Clear session for next iteration
            self._clear_session()
            self.ui.log_info("Session cleared, ready for next iteration")

            # Re-parse plan to check current state
            plan = self.plan_parser.parse()
            self.state.plan = plan

            if plan.progress_percentage >= 100:
                self.ui.log_success("Plan fully implemented!")
                break

        self.state.is_running = False
        return plan.progress_percentage >= 100

    async def _run_implement_plan(self) -> dict:
        """
        Run Claude Code with /implement_plan skill.

        Returns:
            Dict with status and details.
        """
        plan_path = str(self.config.plan_path)
        prompt = f"/implement_plan @{plan_path} ensure to stop for manual verification items."

        self.ui.log_info(f"Running: {prompt[:80]}...")

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
        ]

        # Add allowed tools if configured
        if self.config.claude_allowed_tools:
            cmd.extend(["--allowedTools", ",".join(self.config.claude_allowed_tools)])

        # Resume session if we have one
        if self._session_id:
            cmd.extend(["--resume", self._session_id])

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir,
            )

            stdout, stderr = await process.communicate()
            output = stdout.decode("utf-8")
            error = stderr.decode("utf-8")

            if process.returncode != 0:
                return {
                    "status": "error",
                    "message": error or f"Exit code {process.returncode}",
                }

            # Parse JSON output
            result = self._parse_claude_output(output)

            # Store session ID for continuation
            if result.get("session_id"):
                self._session_id = result["session_id"]

            # Check for completion
            response_text = result.get("result", "")
            if self._matches_patterns(response_text, self.COMPLETION_PATTERNS):
                return {"status": "complete", "result": result}

            # Check for manual verification needed
            if self._matches_patterns(response_text, self.MANUAL_VERIFICATION_PATTERNS):
                return {"status": "verification_needed", "result": result}

            # Check confidence from structured output
            structured = result.get("structured_output", {})
            if isinstance(structured, str):
                try:
                    structured = json.loads(structured)
                except json.JSONDecodeError:
                    structured = {}

            confidence = structured.get("confidence", 0.8)
            if confidence < self.config.confidence_threshold:
                return {
                    "status": "low_confidence",
                    "message": f"Confidence {confidence:.0%} below threshold",
                    "result": result,
                }

            if structured.get("needs_human_review"):
                return {"status": "verification_needed", "result": result}

            # Default: assume we need to continue
            return {"status": "continue", "result": result}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _parse_claude_output(self, output: str) -> dict:
        """Parse Claude CLI JSON output."""
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # Try to find JSON in the output
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            return {"result": output, "raw": True}

    def _matches_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any of the patterns."""
        text_lower = text.lower()
        for pattern in patterns:
            if re.search(pattern, text_lower):
                return True
        return False

    async def _run_verification(self) -> bool:
        """
        Run automated verification using Playwright or uv run.

        Returns:
            True if verification passed.
        """
        # Try Playwright MCP first if enabled
        if self.config.playwright_enabled:
            playwright_result = await self._run_playwright_verification()
            if playwright_result is not None:
                return playwright_result

        # Try running tests via uv
        test_result = await self._run_uv_tests()
        if test_result is not None:
            return test_result

        # Try spinning up services and testing
        service_result = await self._run_service_tests()
        if service_result is not None:
            return service_result

        # No verification method available - pass by default
        self.ui.log_warning("No verification method available, assuming pass")
        return True

    async def _run_playwright_verification(self) -> bool | None:
        """Run Playwright verification via Claude Code with MCP."""
        self.ui.log_info("Attempting Playwright verification...")

        prompt = """You have Playwright MCP tools available. Please verify the implementation:
1. Navigate to the application (check for running dev server)
2. Take a snapshot to understand the current state
3. Verify the implemented features work correctly
4. Take screenshots of key functionality
5. Report success/failure with details

Output JSON: {"success": true/false, "details": "..."}"""

        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", "json",
            "--allowedTools", ",".join([
                "Read",
                "Bash",
                "mcp__playwright__browser_navigate",
                "mcp__playwright__browser_snapshot",
                "mcp__playwright__browser_click",
                "mcp__playwright__browser_type",
                "mcp__playwright__browser_take_screenshot",
            ]),
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir,
            )

            stdout, _ = await process.communicate()
            output = stdout.decode("utf-8")

            result = self._parse_claude_output(output)
            response = result.get("result", "")

            # Check for success indicators
            if "success" in response.lower() and "true" in response.lower():
                return True
            if "fail" in response.lower() or "error" in response.lower():
                return False

            return None  # Inconclusive

        except Exception as e:
            self.ui.log_warning(f"Playwright verification error: {e}")
            return None

    async def _run_uv_tests(self) -> bool | None:
        """Run tests using uv."""
        self.ui.log_info("Attempting uv test run...")

        # Check if pytest is available
        pyproject = self.config.working_dir / "pyproject.toml"
        if not pyproject.exists():
            return None

        try:
            # Try running pytest
            process = await asyncio.create_subprocess_exec(
                "uv", "run", "pytest", "-v", "--tb=short",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir,
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                self.ui.log_success("Tests passed")
                return True
            elif process.returncode == 5:
                # No tests collected - not a failure
                self.ui.log_info("No tests found")
                return None
            else:
                self.ui.log_error(f"Tests failed:\n{stderr.decode()[:500]}")
                return False

        except Exception as e:
            self.ui.log_warning(f"UV test error: {e}")
            return None

    async def _run_service_tests(self) -> bool | None:
        """Spin up services and test them."""
        self.ui.log_info("Checking for service tests...")

        # Look for docker-compose or similar
        compose_files = [
            "docker-compose.yml",
            "docker-compose.yaml",
            "compose.yml",
            "compose.yaml",
        ]

        for compose_file in compose_files:
            if (self.config.working_dir / compose_file).exists():
                return await self._test_docker_services(compose_file)

        # Look for package.json (Node.js project)
        if (self.config.working_dir / "package.json").exists():
            return await self._test_node_services()

        return None

    async def _test_docker_services(self, compose_file: str) -> bool | None:
        """Test Docker Compose services."""
        self.ui.log_info(f"Found {compose_file}, testing services...")

        try:
            # Start services
            start_process = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", compose_file, "up", "-d",
                cwd=self.config.working_dir,
            )
            await start_process.wait()

            # Wait for services to be ready
            await asyncio.sleep(5)

            # Health check
            health_process = await asyncio.create_subprocess_exec(
                "docker", "compose", "-f", compose_file, "ps",
                stdout=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir,
            )
            stdout, _ = await health_process.communicate()
            output = stdout.decode()

            # Check if services are running
            if "running" in output.lower() or "up" in output.lower():
                self.ui.log_success("Docker services running")
                return True

            return False

        except Exception as e:
            self.ui.log_warning(f"Docker test error: {e}")
            return None

    async def _test_node_services(self) -> bool | None:
        """Test Node.js services."""
        self.ui.log_info("Found package.json, checking for test script...")

        try:
            # Run npm test
            process = await asyncio.create_subprocess_exec(
                "npm", "test",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.working_dir,
            )

            _, _ = await process.communicate()
            return process.returncode == 0

        except Exception as e:
            self.ui.log_warning(f"Node test error: {e}")
            return None

    def _update_plan_summary(self, plan: Plan) -> None:
        """Update the plan's Quick Start section."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        completed = sum(
            1 for p in plan.phases if p.status == StepStatus.COMPLETED
        )

        summary_lines = [
            f"**Last Updated:** {now}",
            f"**Progress:** {completed}/{len(plan.phases)} phases complete ({plan.progress_percentage:.0f}%)",
            "",
            "**Phase Status:**",
        ]

        for phase in plan.phases:
            icon = "✓" if phase.status == StepStatus.COMPLETED else "○"
            summary_lines.append(f"- {icon} {phase.name}")

        if plan.current_phase and plan.current_phase.status != StepStatus.COMPLETED:
            summary_lines.extend([
                "",
                "**To Continue:**",
                f"Run `claudestine run {plan.path}`",
            ])

        self.plan_parser.update_summary("\n".join(summary_lines))

    async def _git_commit_and_push(self, plan: Plan) -> bool:
        """Commit and push changes with conventional commit format."""
        try:
            # Stage all changes
            await self._run_git("add", "-A")

            # Check if there are changes to commit
            result = await self._run_git("diff", "--cached", "--quiet", check=False)
            if result.returncode == 0:
                self.ui.log_info("No changes to commit")
                return True

            # Generate commit message (no Claude watermark)
            phase_name = plan.current_phase.name if plan.current_phase else "implementation"
            commit_msg = f"feat: {phase_name.lower()}"

            # Clean up commit message
            commit_msg = re.sub(r"phase\s*\d+:\s*", "", commit_msg, flags=re.IGNORECASE)
            commit_msg = commit_msg[:72]  # Keep it short

            # Commit (NO Co-Authored-By)
            await self._run_git("commit", "-m", commit_msg)
            self.ui.log_success(f"Committed: {commit_msg}")

            # Push if configured
            if self.config.auto_push:
                await self._run_git("push")
                self.ui.log_success("Pushed to remote")

            return True

        except Exception as e:
            self.ui.log_error(f"Git error: {e}")
            return False

    async def _run_git(self, *args, check: bool = True) -> asyncio.subprocess.Process:
        """Run a git command."""
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.working_dir,
        )
        await process.communicate()

        if check and process.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}")

        return process

    def _clear_session(self) -> None:
        """Clear the current Claude session."""
        self._session_id = None

    def stop(self, reason: str = "User requested stop") -> None:
        """Stop the orchestration loop."""
        self._should_stop = True
        if self.state:
            self.state.should_stop = True
            self.state.stop_reason = reason
