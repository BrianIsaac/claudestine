# Claudestine

Automated plan implementation orchestrator for Claude Code.

Claudestine wraps Claude Code's `/implement_plan` skill and automates the full implementation loop:

```
┌─────────────────────────────────────────────────────────────┐
│                    CLAUDESTINE LOOP                         │
├─────────────────────────────────────────────────────────────┤
│  1. claude "/implement_plan @{plan}"                        │
│     └─> Runs until completion OR manual verification        │
│                                                             │
│  2. Automated verification                                  │
│     ├─> Playwright MCP tests                                │
│     ├─> uv run pytest                                       │
│     └─> Docker compose health checks                        │
│                                                             │
│  3. Update plan summary (Quick Start section)               │
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

# Option 3: Editable install
cd /path/to/claudestine
uv pip install -e .
```

## Usage

```bash
# From your project directory
cd ~/my-project

# Run with TUI dashboard
claudestine run thoughts/shared/plans/my-feature.md

# Run headless (CI/terminal)
claudestine run plan.md --headless

# Disable auto-push (local commits only)
claudestine run plan.md --no-auto-push

# Higher confidence threshold
claudestine run plan.md -c 0.9

# Preview plan structure without running
claudestine preview plan.md
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `-w, --working-dir` | Auto-detect | Working directory for Claude Code |
| `-c, --confidence-threshold` | 0.8 | Minimum confidence to continue (0-1) |
| `--auto-commit/--no-auto-commit` | enabled | Commit after each iteration |
| `--auto-push/--no-auto-push` | enabled | Push after commit |
| `--playwright/--no-playwright` | enabled | Use Playwright MCP for verification |
| `--headless` | disabled | Run without TUI |

## TUI Controls

| Key | Action |
|-----|--------|
| `q` | Quit |
| `p` | Pause/Resume |
| `s` | Stop |
| `c` | Clear log |

## Stop Conditions

Claudestine automatically stops when:

- All phases complete
- Claude reports low confidence (below threshold)
- Verification fails
- Claude indicates human review needed
- User presses `s` or `q`

## Requirements

- Python 3.12+
- Claude Code CLI installed and configured
- uv package manager
