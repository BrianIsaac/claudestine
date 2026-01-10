# Claudestine

Automated plan implementation orchestrator for Claude Code.

## Why Claudestine?

When implementing large features with Claude Code, **context management becomes critical**. As Claude works through a complex plan, the context window fills up with file contents, tool outputs, and conversation history. Eventually:

- Claude starts forgetting earlier decisions
- Responses become slower and more expensive
- Quality degrades as important context gets pushed out

The typical approach is to one-shot an entire plan, but this fails for larger implementations.

Claudestine solves this by **managing context during plan implementation**. You still create and iterate on plans using the included `/create_plan` slash command (or manually), but when it's time to implement, Claudestine executes phase by phase:

1. Implements a single phase from the plan
2. Runs automated verification (Playwright, pytest, etc.)
3. Updates the plan summary for session continuity
4. Commits changes and clears the session
5. Loops back with fresh context for the next phase

The result: Claude always operates within reasonable context limits while maintaining continuity across the full implementation through the plan file.

## Features

- **Phase-by-phase execution** - Implements one phase at a time, loops automatically
- **Real-time streaming output** - See Claude's responses as they happen
- **Context window tracking** - Header shows `Context: 45k/200k (22.5%)` in real-time
- **Full tool visibility** - See exactly what Claude is doing (file paths, commands, diffs)
- **Interactive controls** - Press P to pause, C to continue, M for manual override
- **Phase tracking** - UI shows `Phase 1/2 | Step 3/5`
- **Readable logs** - Markdown logs with collapsible sections in `.claudestine/logs/`
- **Configurable workflow** - YAML-based, editable before execution
- **Auto verification** - Playwright MCP, pytest, Docker health checks
- **Conventional commits** - No Claude watermark
- **Interactive mode** - Plan and workflow selection with prompts

## Overview

Claudestine wraps Claude Code and automates the implementation loop. The default workflow (what I typically use) looks like this, but [custom workflows](#configuration) can be configured:

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

## Credits

The `.claude/` subagents and slash commands are based on [HumanLayer](https://github.com/humanlayer/humanlayer)'s Claude Code configuration. The agents have been updated to add LSP support.
