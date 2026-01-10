"""Data models for Claudestine orchestrator."""

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Status of a step or phase."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Step(BaseModel):
    """An individual step within a phase."""

    description: str
    status: StepStatus = StepStatus.PENDING
    requires_verification: bool = False
    verification_command: str | None = None


class Phase(BaseModel):
    """A phase of the implementation plan."""

    name: str
    description: str = ""
    status: StepStatus = StepStatus.PENDING
    steps: list[Step] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    """The overall implementation plan."""

    path: Path
    title: str
    summary: str = ""
    phases: list[Phase] = Field(default_factory=list)
    current_phase_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def current_phase(self) -> Phase | None:
        """Get the current phase being worked on."""
        if 0 <= self.current_phase_index < len(self.phases):
            return self.phases[self.current_phase_index]
        return None

    @property
    def progress_percentage(self) -> float:
        """Calculate overall progress as a percentage."""
        if not self.phases:
            return 0.0
        completed = sum(1 for p in self.phases if p.status == StepStatus.COMPLETED)
        return (completed / len(self.phases)) * 100


class ClaudeResponse(BaseModel):
    """Structured response from Claude Code execution."""

    success: bool
    confidence: float = Field(ge=0.0, le=1.0)
    completed_steps: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    needs_human_review: bool = False
    session_id: str | None = None
    raw_output: str = ""
    error_message: str | None = None


class VerificationResult(BaseModel):
    """Result of a verification step."""

    success: bool
    details: str = ""
    assertions_passed: int = 0
    assertions_total: int = 0
    screenshot_paths: list[Path] = Field(default_factory=list)
    error_message: str | None = None


class OrchestratorConfig(BaseModel):
    """Configuration for the orchestrator."""

    plan_path: Path
    working_dir: Path
    confidence_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    auto_commit: bool = False
    auto_push: bool = False
    max_retries: int = 2
    claude_allowed_tools: list[str] = Field(
        default_factory=lambda: ["Read", "Edit", "Write", "Bash", "Glob", "Grep"]
    )
    playwright_enabled: bool = True


class OrchestratorState(BaseModel):
    """Current state of the orchestrator."""

    plan: Plan
    config: OrchestratorConfig
    current_session_id: str | None = None
    logs: list[str] = Field(default_factory=list)
    is_running: bool = False
    should_stop: bool = False
    stop_reason: str | None = None
