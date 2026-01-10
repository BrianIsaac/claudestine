# Claudestine

Automated plan implementation orchestrator for Claude Code.

## Overview

Claudestine wraps Claude Code and automates the full implementation loop:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLAUDESTINE LOOP                         │
│                  (runs per phase in plan)                   │
├─────────────────────────────────────────────────────────────┤
│  1. Implement next phase from plan                          │
│     └─> Stops after completing one phase                    │
│                                                             │
│  2. Automated verification                                  │
│     ├─> Playwright MCP tests                                │
│     ├─> uv run commands                                     │
│     └─> Service health checks                               │
│                                                             │
│  3. Update plan summary for session continuity              │
│                                                             │
│  4. Git commit (conventional, no watermark) + push          │
│                                                             │
│  5. Clear session, loop back to step 1                      │
└─────────────────────────────────────────────────────────────┘
```

## Installation

```bash
# Install as UV tool (recommended for use across repos)
uv tool install /path/to/claudestine

# Or add to your PATH after install
uv tool install ~/Documents/personal/claudestine
```

## Usage

### Interactive Mode (Recommended)

Navigate to any project with a plan file and run:

```bash
cd ~/Documents/personal/my-project
claudestine
```

This launches interactive mode where you can:
1. Select a plan from auto-discovered `.md` files
2. Choose a workflow (default, project, global, or custom)
3. Configure options (auto-push, etc.)
4. Start execution

### Direct Mode

```bash
# Run with default workflow
claudestine run path/to/plan.md

# Edit workflow before running
claudestine run plan.md --edit

# Dry run (show what would happen)
claudestine run plan.md --dry-run

# Disable auto-push
claudestine run plan.md --no-push

# Use custom workflow
claudestine run plan.md --workflow my-workflow.yaml
```

## Using in Other Repos

Claudestine works from any directory. When you run it:

1. **Working directory** is auto-detected as the git root of the plan file
2. **Logs** are stored in `<working-dir>/.claudestine/logs/`
3. **Project workflow** can be customised at `<working-dir>/.claudestine/workflow.yaml`

### Example: Using in another project

```bash
# Install claudestine once
uv tool install ~/Documents/personal/claudestine

# Navigate to any project
cd ~/Documents/personal/other-project

# Run claudestine (will find plans in current directory)
claudestine

# Or specify a plan directly
claudestine run thoughts/plans/feature-x.md
```

### Where do logs go?

Logs appear in the **target project**, not in claudestine:

```
~/Documents/personal/other-project/
├── .claudestine/
│   └── logs/
│       └── 20260110_120000_feature-x.md   # Readable markdown log
├── thoughts/
│   └── plans/
│       └── feature-x.md
└── src/
    └── ...
```

## Workflow Commands

```bash
# Show current workflow
claudestine workflow show

# Create project-specific workflow
claudestine workflow init --scope project

# Create global workflow (applies to all projects)
claudestine workflow init --scope global

# Edit workflow (opens in $EDITOR)
claudestine workflow edit

# Reset to defaults
claudestine workflow reset
```

## Configuration

Workflows are loaded with precedence:

1. **Project**: `<project>/.claudestine/workflow.yaml`
2. **Global**: `~/.config/claudestine/workflow.yaml`
3. **Bundled**: Default workflow

### Default Workflow

The default workflow runs these Claude prompts per phase:

```yaml
name: Implementation Loop
version: 1

steps:
  - name: implement
    type: claude
    prompt: |
      Read @{plan_path} and implement ONLY the next incomplete phase.
      Do not implement multiple phases - stop after completing one phase.
      Update the phase status to "complete" when done.

  - name: verify
    type: claude
    prompt: |
      You do the manual testing for me. You may use either:
      - Playwright MCP to test the UI
      - uv run -c to run test commands
      - Spin up services and test endpoints
      Ensure everything is working. Report success/failure with details.

  - name: update_summary
    type: claude
    prompt: |
      Update the summary at the top of the plan ({plan_path}) so the next
      session can understand and continue. Include:
      - Current progress percentage
      - What was completed this session
      - What's next

  - name: commit
    type: claude
    prompt: |
      Git commit with conventional commits on all the changes.
      Do not leave a claude code watermark. Push the changes.

  - name: clear
    type: internal
    action: clear_session
```

### Step Types

| Type | Description |
|------|-------------|
| `claude` | Run Claude Code with prompt |
| `shell` | Run shell commands directly |
| `internal` | Internal actions (clear_session) |

### Variables

Available in prompts and commands:

| Variable | Description |
|----------|-------------|
| `{plan_path}` | Full path to the plan file |
| `{working_dir}` | Working directory |

## Features

- **Phase-by-phase execution** - Implements one phase at a time, loops automatically
- **Real-time streaming output** - See Claude's responses as they happen
- **Phase tracking** - UI shows `Phase 1/2 | Step 3/5`
- **Readable logs** - Markdown logs with collapsible sections in `.claudestine/logs/`
- **Configurable workflow** - YAML-based, editable before execution
- **Auto verification** - Playwright MCP, pytest, Docker health checks
- **Conventional commits** - No Claude watermark
- **Interactive mode** - Plan and workflow selection with prompts

## Plan Format

Plans should have phases marked with `## Phase X` headers:

```markdown
# My Feature Plan

## Quick Start
**Progress:** 0/3 phases complete (0%)

## Phase 1: Setup
**Status:** pending
### Steps
1. Do something
### Success Criteria
- [ ] Something works

## Phase 2: Implementation
**Status:** pending
...

## Phase 3: Testing
**Status:** pending
...
```

Claudestine will:
- Count phases automatically
- Implement one phase per loop iteration
- Check for completion by looking at phase statuses

## Requirements

- Python 3.12+
- Claude Code CLI installed and configured
- uv package manager
