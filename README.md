# Claudestine

Automated plan creation and implementation orchestrator for Claude Code.

## Why Claudestine?

When implementing large features with Claude Code, **context management becomes critical**. As Claude works through a complex plan, the context window fills up with file contents, tool outputs, and conversation history. Eventually:

- Claude starts forgetting earlier decisions
- Responses become slower and more expensive
- Quality degrades as important context gets pushed out

The typical approach is to one-shot an entire plan, but this fails for larger implementations.

Claudestine solves this by **managing context at two key stages**:

1. **Plan Creation** - Research the codebase, create a grounded implementation plan, and verify all claims before you start coding
2. **Plan Implementation** - Execute phase by phase with automatic context clearing between phases

For both stages, Claudestine orchestrates Claude Code sessions, managing context so you get consistent quality throughout.

## Features

- **Plan creation with verification** - Research codebase, create plan, verify all claims before coding
- **Phase-by-phase implementation** - Implements one phase at a time, loops automatically
- **Real-time streaming output** - See Claude's responses as they happen
- **Context window tracking** - Header shows `Context: 45k/200k (22.5%)` in real-time
- **Full tool visibility** - See exactly what Claude is doing (file paths, commands, diffs)
- **Interactive controls** - Press P to pause, C to continue, M for manual override
- **Phase tracking** - UI shows `Phase 1/2 | Step 3/5`
- **Readable logs** - Markdown logs with collapsible sections in `.claudestine/logs/`
- **Configurable workflows** - YAML-based, separate workflows for create and implement
- **Auto verification** - Playwright MCP, pytest, Docker health checks
- **Conventional commits** - No Claude watermark
- **Interactive mode** - Plan and workflow selection with prompts

## Overview

Claudestine wraps Claude Code and automates two key workflows. [Custom workflows](#configuration) can be configured.

### Create Mode

Creates a verified implementation plan grounded in actual codebase research:

```
┌─────────────────────────────────────────────────────────────┐
│                   CREATE PLAN WORKFLOW                      │
├─────────────────────────────────────────────────────────────┤
│  Phase 1 (once):                                            │
│  1. Research codebase using subagents                       │
│     └─> codebase-locator, codebase-analyzer, etc.           │
│  2. Outline implementation plan from research               │
│  3. Write plan to file with meaningful name                 │
│  4. Clear session                                           │
├─────────────────────────────────────────────────────────────┤
│  Verification loop (until verified):                        │
│  5. Verify all claims against codebase                      │
│     └─> If all verified: add "## Status: Verified"          │
│     └─> If issues found: report them                        │
│  6. Update plan to fix inaccuracies (if needed)             │
│  7. Clear session, loop back to step 5                      │
└─────────────────────────────────────────────────────────────┘
```

### Implement Mode

Executes a plan phase by phase with context clearing between phases:

```
┌─────────────────────────────────────────────────────────────┐
│                  IMPLEMENT PLAN WORKFLOW                    │
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

> **Note:** Even with automated implementation, you should still read and understand the plan before running it. The plan documents what will change in your codebase - review it to ensure it aligns with your intentions and catch any issues before code is written.

## Installation

### Prerequisites

- Python 3.12+
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) installed and configured
- [uv](https://docs.astral.sh/uv/) package manager
- [git](https://git-scm.com/)

### Recommended MCP Servers

For full functionality, configure these MCP servers in Claude Code:

- **[Playwright MCP](https://github.com/anthropics/anthropic-quickstarts/tree/main/mcp-server-playwright)** - Automated browser testing for UI verification
- **[pyright-lsp](https://github.com/anthropics/anthropic-quickstarts/tree/main/mcp-server-pyright)** - Python language server for type checking and code intelligence (used by subagents)

### Install

```bash
# Clone the repo
git clone https://github.com/BrianIsaac/claudestine.git

# Install as UV tool (recommended for use across repos)
uv tool install ./claudestine
```

## Usage

### Interactive Mode (Recommended)

Navigate to any project and run:

```bash
cd ~/Documents/personal/my-project
claudestine
```

This launches interactive mode where you:
1. Choose mode: **Create** a new plan or **Implement** an existing one
2. For create mode: enter research topic and context
3. For implement mode: select a plan from auto-discovered `.md` files
4. Choose a workflow (default, project, global, or custom)
5. Configure options (auto-push, etc.)
6. Start execution

### Direct Mode

```bash
# Implement an existing plan
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

### Keyboard Controls

During execution, you can control claudestine with these keys:

| Key | Action |
|-----|--------|
| `P` | Pause execution |
| `C` | Continue after pause |
| `M` | Manual mode - enter a custom prompt |
| `Ctrl+C` | Stop completely |

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

## Configuration

Workflows are loaded with precedence:

1. **Project**: `<project>/.claudestine/workflow.yaml`
2. **Global**: `~/.config/claudestine/workflow.yaml`
3. **Bundled**: Default workflow

### Workflow Commands

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

### Default Workflow (Implement Mode)

The default implementation workflow runs these Claude prompts per phase:

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

### Create Plan Workflow

The create workflow researches, creates, and verifies a plan:

```yaml
name: Create Plan
version: 1

steps:
  # Phase 1 only - research and create
  - name: research
    type: claude
    prompt: |
      /research_codebase {research_topic}
      Use codebase-locator, codebase-analyzer, and codebase-pattern-finder
      subagents to thoroughly research the codebase.
    first_phase_only: true

  - name: outline_plan
    type: claude
    prompt: |
      /create_plan for the research done.
      Context: {context}
      Create a detailed implementation plan based on the research findings.
    first_phase_only: true

  - name: write_plan
    type: claude
    prompt: |
      Write the complete plan to {plan_directory}/ with a meaningful filename.
      Use format: YYYY-MM-DD-description.md
    first_phase_only: true

  - name: clear
    type: internal
    action: clear_session

  # Verification loop
  - name: verify
    type: claude
    prompt: |
      Find the most recently created .md file in {plan_directory}/.
      Verify each factual claim about the codebase.
      If ALL claims verified: add "## Status: Verified" at the top.
      If issues found: report them for the next step to fix.

  - name: update
    type: claude
    prompt: |
      Find the plan in {plan_directory}/.
      If already verified, do nothing.
      Otherwise, fix inaccuracies based on the verification report.

  - name: clear_loop
    type: internal
    action: clear_session
```

### Step Types

| Type | Description |
|------|-------------|
| `claude` | Run Claude Code with prompt |
| `shell` | Run shell commands directly |
| `internal` | Internal actions (clear_session) |

### Step Options

| Option | Description |
|--------|-------------|
| `first_phase_only` | Only run this step in phase 1 (useful for setup steps) |
| `require_success` | Fail workflow if this step fails |
| `skip_if_clean` | Skip shell step if git working tree is clean |
| `stream` | Stream Claude output in real-time (default: true) |
| `stop_on` | List of patterns that trigger step completion |

### Variables

Available in prompts and commands:

| Variable | Description |
|----------|-------------|
| `{plan_path}` | Full path to the plan file (implement mode) |
| `{plan_directory}` | Directory for plan output (create mode) |
| `{research_topic}` | Research topic input (create mode) |
| `{context}` | Additional context input (create mode) |
| `{working_dir}` | Working directory |

## Credits

The `.claude/` subagents and slash commands are based on [HumanLayer](https://github.com/humanlayer/humanlayer)'s Claude Code configuration. The agents have been updated to add LSP support.
