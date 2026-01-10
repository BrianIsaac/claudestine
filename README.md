# Claudestine

Automated plan implementation orchestrator for Claude Code.

## Overview

Claudestine wraps Claude Code and automates the full implementation loop:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLAUDESTINE LOOP                         │
├─────────────────────────────────────────────────────────────┤
│  1. /implement_plan @{plan}                                 │
│     └─> Runs until completion OR verification needed        │
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
# Option 1: Install as UV tool (recommended)
uv tool install /path/to/claudestine

# Option 2: Run directly without installing
uv run --project /path/to/claudestine claudestine run <plan>
```

## Usage

```bash
# Run with default workflow
claudestine run plan.md

# Edit workflow before running
claudestine run plan.md --edit

# Dry run (show what would happen)
claudestine run plan.md --dry-run

# Disable auto-push
claudestine run plan.md --no-push

# Use custom workflow
claudestine run plan.md --workflow my-workflow.yaml
```

## Workflow Commands

```bash
# Show current workflow
claudestine workflow show

# Create project-specific workflow
claudestine workflow init --scope project

# Create global workflow
claudestine workflow init --scope global

# Edit workflow (opens in $EDITOR)
claudestine workflow edit

# Reset to defaults
claudestine workflow reset
```

## Configuration

Workflows are loaded with precedence:

1. **Project**: `.claudestine/workflow.yaml`
2. **Global**: `~/.config/claudestine/workflow.yaml`
3. **Bundled**: Default workflow

### Workflow Format

```yaml
name: Implementation Loop
version: 1

steps:
  - name: implement
    type: claude
    prompt: |
      /implement_plan @{plan_path} ensure to stop for manual verification items.
    stream: true
    stop_on:
      - "manual verification"
      - "needs human review"

  - name: verify
    type: claude
    prompt: |
      You do the manual testing for me...
    require_success: true

  - name: commit
    type: shell
    commands:
      - git add -A
      - git commit -m "{commit_message}"
      - git push
    skip_if_clean: true

  - name: clear
    type: internal
    action: clear_session
```

### Step Types

| Type | Description |
|------|-------------|
| `claude` | Run Claude Code with prompt |
| `shell` | Run shell commands directly |
| `internal` | Internal actions (clear_session, show_changes) |

### Variables

Available in prompts and commands:

| Variable | Description |
|----------|-------------|
| `{plan_path}` | Full path to the plan file |
| `{working_dir}` | Working directory |
| `{commit_message}` | Auto-generated conventional commit message |

## Features

- **Real-time streaming output** - See Claude's responses as they happen
- **Collapsible sections** - Clean UI that collapses completed steps
- **Configurable workflow** - YAML-based, editable before execution
- **Auto verification** - Playwright MCP, pytest, Docker health checks
- **Conventional commits** - No Claude watermark
- **Stop conditions** - Automatic stops on low confidence or verification needs

## Requirements

- Python 3.12+
- Claude Code CLI installed and configured
- uv package manager
