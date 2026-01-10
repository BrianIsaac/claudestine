"""Configuration models for Claudestine."""

from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class StepType(str, Enum):
    """Type of workflow step."""

    CLAUDE = "claude"
    SHELL = "shell"
    INTERNAL = "internal"


class StopCondition(BaseModel):
    """Condition that triggers step completion."""

    pattern: str
    action: str = "stop"  # stop, pause, fail


class Step(BaseModel):
    """A single step in the workflow."""

    name: str
    type: StepType = StepType.CLAUDE
    prompt: str | None = None
    commands: list[str] | None = None
    action: str | None = None
    stream: bool = True
    stop_on: list[str] = Field(default_factory=list)
    require_success: bool = False
    skip_if_clean: bool = False
    allowed_tools: list[str] | None = None


class Workflow(BaseModel):
    """A complete workflow definition."""

    name: str
    version: int = 1
    description: str = ""
    steps: list[Step]
    variables: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "Workflow":
        """Load workflow from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def to_yaml(self) -> str:
        """Export workflow to YAML string."""
        # Convert to dict with enum values as strings
        data = self.model_dump(exclude_none=True, mode="json")
        return yaml.dump(
            data,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    def save(self, path: Path) -> None:
        """Save workflow to YAML file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.to_yaml())


class RunConfig(BaseModel):
    """Configuration for a single run."""

    plan_path: Path
    working_dir: Path
    workflow_path: Path | None = None
    auto_push: bool = True
    dry_run: bool = False
    verbose: bool = False


def get_config_dir() -> Path:
    """Get the global config directory."""
    return Path.home() / ".config" / "claudestine"


def get_project_config_dir(working_dir: Path) -> Path:
    """Get the project-specific config directory."""
    return working_dir / ".claudestine"


def find_workflow(working_dir: Path, workflow_name: str | None = None) -> Path | None:
    """
    Find workflow file with precedence: project > global > bundled.

    Args:
        working_dir: Project working directory.
        workflow_name: Optional specific workflow name.

    Returns:
        Path to workflow file, or None if not found.
    """
    filename = f"{workflow_name}.yaml" if workflow_name else "workflow.yaml"

    # 1. Project-specific
    project_path = get_project_config_dir(working_dir) / filename
    if project_path.exists():
        return project_path

    # 2. Global config
    global_path = get_config_dir() / filename
    if global_path.exists():
        return global_path

    # 3. Bundled default
    bundled_path = Path(__file__).parent.parent.parent / "workflows" / "default.yaml"
    if bundled_path.exists():
        return bundled_path

    return None


def load_workflow(
    working_dir: Path,
    workflow_path: Path | None = None,
) -> Workflow:
    """
    Load workflow with fallback chain.

    Args:
        working_dir: Project working directory.
        workflow_path: Optional explicit workflow path.

    Returns:
        Loaded Workflow instance.

    Raises:
        FileNotFoundError: If no workflow found.
    """
    if workflow_path and workflow_path.exists():
        return Workflow.from_yaml(workflow_path)

    found_path = find_workflow(working_dir)
    if found_path:
        return Workflow.from_yaml(found_path)

    raise FileNotFoundError(
        "No workflow found. Create one with: claudestine workflow init"
    )
