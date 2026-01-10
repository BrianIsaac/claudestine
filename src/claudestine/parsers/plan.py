"""Parser for implementation plan markdown files."""

import re
from pathlib import Path

from claudestine.models import Phase, Plan, Step, StepStatus


class PlanParser:
    """Parses markdown implementation plans into structured Plan objects."""

    PHASE_PATTERN = re.compile(
        r"^##\s*Phase\s*(\d+)[:\s]*(.+?)(?:\s*\(([^)]+)\))?$",
        re.IGNORECASE | re.MULTILINE,
    )
    STATUS_TABLE_PATTERN = re.compile(
        r"\|\s*Phase\s*(\d+)\s*\|[^|]*\|[^|]*\*{0,2}(COMPLETE|Pending|IN PROGRESS|FAILED)[^|]*\*{0,2}\s*\|",
        re.IGNORECASE,
    )
    TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
    STEP_PATTERNS = [
        re.compile(r"^\s*[-*]\s+(.+)$", re.MULTILINE),
        re.compile(r"^\s*\d+\.\s+(.+)$", re.MULTILINE),
    ]
    SUCCESS_CRITERIA_PATTERN = re.compile(
        r"(?:Success\s*Criteria|Verification)[:\s]*\n((?:[-*\d].*\n?)+)",
        re.IGNORECASE,
    )
    VERIFICATION_PATTERN = re.compile(
        r"(?:manual\s*verification|verify\s*manually|human\s*review)",
        re.IGNORECASE,
    )

    def __init__(self, plan_path: Path):
        """
        Initialise the plan parser.

        Args:
            plan_path: Path to the markdown plan file.
        """
        self.plan_path = plan_path
        self._content: str | None = None

    def parse(self) -> Plan:
        """
        Parse the plan file into a structured Plan object.

        Returns:
            Parsed Plan object with phases and steps.
        """
        self._content = self.plan_path.read_text(encoding="utf-8")

        title = self._extract_title()
        summary = self._extract_summary()
        phases = self._extract_phases()
        phase_statuses = self._extract_phase_statuses()

        for phase in phases:
            phase_num = self._extract_phase_number(phase.name)
            if phase_num and phase_num in phase_statuses:
                phase.status = phase_statuses[phase_num]

        current_index = 0
        for i, phase in enumerate(phases):
            if phase.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS):
                current_index = i
                break

        return Plan(
            path=self.plan_path,
            title=title,
            summary=summary,
            phases=phases,
            current_phase_index=current_index,
        )

    def _extract_title(self) -> str:
        """Extract the plan title from the first heading."""
        if not self._content:
            return "Untitled Plan"

        match = self.TITLE_PATTERN.search(self._content)
        if match:
            return match.group(1).strip()
        return "Untitled Plan"

    def _extract_summary(self) -> str:
        """Extract the summary section from the plan."""
        if not self._content:
            return ""

        quick_start_match = re.search(
            r"##\s*Quick\s*Start.*?\n(.*?)(?=\n##\s|\n---|\Z)",
            self._content,
            re.IGNORECASE | re.DOTALL,
        )
        if quick_start_match:
            return quick_start_match.group(1).strip()

        summary_match = re.search(
            r"##\s*(?:Summary|Overview).*?\n(.*?)(?=\n##\s|\n---|\Z)",
            self._content,
            re.IGNORECASE | re.DOTALL,
        )
        if summary_match:
            return summary_match.group(1).strip()

        return ""

    def _extract_phases(self) -> list[Phase]:
        """Extract all phases from the plan."""
        if not self._content:
            return []

        phases: list[Phase] = []
        matches = list(self.PHASE_PATTERN.finditer(self._content))

        for i, match in enumerate(matches):
            phase_num = match.group(1)
            phase_title = match.group(2).strip()
            inline_status = match.group(3)

            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(self._content)
            phase_content = self._content[start:end]

            status = StepStatus.PENDING
            if inline_status:
                status = self._parse_status(inline_status)

            steps = self._extract_steps(phase_content)
            success_criteria = self._extract_success_criteria(phase_content)

            phases.append(
                Phase(
                    name=f"Phase {phase_num}: {phase_title}",
                    description=phase_content[:500].strip(),
                    status=status,
                    steps=steps,
                    success_criteria=success_criteria,
                )
            )

        return phases

    def _extract_steps(self, content: str) -> list[Step]:
        """Extract steps from phase content."""
        steps: list[Step] = []
        seen_descriptions: set[str] = set()

        for pattern in self.STEP_PATTERNS:
            for match in pattern.finditer(content):
                desc = match.group(1).strip()
                if desc and desc not in seen_descriptions and len(desc) > 5:
                    seen_descriptions.add(desc)
                    requires_verification = bool(
                        self.VERIFICATION_PATTERN.search(desc)
                    )
                    steps.append(
                        Step(
                            description=desc,
                            requires_verification=requires_verification,
                        )
                    )

        return steps

    def _extract_success_criteria(self, content: str) -> list[str]:
        """Extract success criteria from phase content."""
        match = self.SUCCESS_CRITERIA_PATTERN.search(content)
        if not match:
            return []

        criteria_text = match.group(1)
        criteria: list[str] = []
        for line in criteria_text.split("\n"):
            line = line.strip()
            line = re.sub(r"^[-*\d.]+\s*", "", line)
            if line:
                criteria.append(line)

        return criteria

    def _extract_phase_statuses(self) -> dict[str, StepStatus]:
        """Extract phase statuses from status table if present."""
        if not self._content:
            return {}

        statuses: dict[str, StepStatus] = {}
        for match in self.STATUS_TABLE_PATTERN.finditer(self._content):
            phase_num = match.group(1)
            status_text = match.group(2)
            statuses[phase_num] = self._parse_status(status_text)

        return statuses

    def _parse_status(self, status_text: str) -> StepStatus:
        """Parse status text into StepStatus enum."""
        status_lower = status_text.lower().strip()
        if "complete" in status_lower:
            return StepStatus.COMPLETED
        elif "progress" in status_lower:
            return StepStatus.IN_PROGRESS
        elif "fail" in status_lower:
            return StepStatus.FAILED
        elif "skip" in status_lower:
            return StepStatus.SKIPPED
        return StepStatus.PENDING

    def _extract_phase_number(self, phase_name: str) -> str | None:
        """Extract the phase number from a phase name."""
        match = re.search(r"Phase\s*(\d+)", phase_name, re.IGNORECASE)
        return match.group(1) if match else None

    def update_summary(self, new_summary: str) -> None:
        """
        Update the summary section in the plan file.

        Args:
            new_summary: New summary content to write.
        """
        content = self.plan_path.read_text(encoding="utf-8")

        quick_start_pattern = re.compile(
            r"(##\s*Quick\s*Start[^\n]*\n)(.*?)(\n##\s|\n---|\Z)",
            re.IGNORECASE | re.DOTALL,
        )
        match = quick_start_pattern.search(content)

        if match:
            new_content = (
                content[: match.start()]
                + match.group(1)
                + "\n"
                + new_summary
                + "\n"
                + match.group(3)
                + content[match.end() :]
            )
            self.plan_path.write_text(new_content, encoding="utf-8")
        else:
            lines = content.split("\n")
            insert_pos = 1
            for i, line in enumerate(lines):
                if line.startswith("# "):
                    insert_pos = i + 1
                    break

            lines.insert(insert_pos, f"\n## Quick Start for New Sessions\n\n{new_summary}\n")
            self.plan_path.write_text("\n".join(lines), encoding="utf-8")

    def update_phase_status(self, phase_index: int, status: StepStatus) -> None:
        """
        Update a phase's status in the plan file.

        Args:
            phase_index: Index of the phase to update.
            status: New status for the phase.
        """
        content = self.plan_path.read_text(encoding="utf-8")
        phase_num = str(phase_index + 1)

        status_map = {
            StepStatus.COMPLETED: "**COMPLETE**",
            StepStatus.IN_PROGRESS: "**IN PROGRESS**",
            StepStatus.PENDING: "Pending",
            StepStatus.FAILED: "**FAILED**",
            StepStatus.SKIPPED: "Skipped",
        }
        status_text = status_map.get(status, "Pending")

        table_pattern = re.compile(
            rf"(\|\s*Phase\s*{phase_num}\s*\|[^|]*\|)[^|]*(\|)",
            re.IGNORECASE,
        )
        new_content = table_pattern.sub(rf"\1 {status_text} \2", content)

        self.plan_path.write_text(new_content, encoding="utf-8")
