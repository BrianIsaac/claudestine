---
name: plan-implementer
description: Implement technical plans methodically with phase-by-phase execution and verification checkpoints. Use this skill when following a detailed implementation plan that has phased changes and success criteria. The skill guides through each phase, verifies completion, and pauses for human confirmation before proceeding to the next phase.
---

# Plan Implementer

## Overview

This skill implements technical plans methodically, following a phase-by-phase approach with verification checkpoints. It is designed to follow plan intent while adapting to reality, ensuring each phase is complete before moving forward.

## Configuration

Customise these paths and commands for your project:

- **`plan_dir`**: Where plans are stored (default: `docs/plans/`)
- **`verification_commands`**: Commands to run for automated verification (default: `make test`, `make lint`)
- **`plan_format`**: Expected plan file format (default: Markdown with checkboxes)

## Getting Started

When given a plan path:

1. **Read the plan completely** and check for any existing checkmarks (- [x])
2. **Read the original ticket** and all files mentioned in the plan
3. **Read files fully** - never use limit/offset parameters, you need complete context
4. **Think deeply** about how the pieces fit together
5. **Create a todo list** to track your progress
6. **Start implementing** if you understand what needs to be done

If no plan path provided, ask for one.

## Implementation Philosophy

Plans are carefully designed, but reality can be messy. The job is to:

- **Follow the plan's intent** while adapting to what you find
- **Implement each phase fully** before moving to the next
- **Verify your work** makes sense in the broader codebase context
- **Update checkboxes** in the plan as you complete sections

When things don't match the plan exactly, think about why and communicate clearly. The plan is your guide, but your judgement matters too.

### Handling Mismatches

If you encounter a mismatch between the plan and reality:

1. **STOP** and think deeply about why the plan can't be followed
2. **Present the issue clearly**:
   ```
   Issue in Phase [N]:
   Expected: [what the plan says]
   Found: [actual situation]
   Why this matters: [explanation]

   How should I proceed?
   ```
3. **Wait for guidance** before continuing

## Verification Approach

After implementing a phase:

1. **Run the success criteria checks** (usually verification commands cover everything)
2. **Fix any issues** before proceeding
3. **Update your progress** in both the plan and your todos
4. **Check off completed items** in the plan file itself using Edit
5. **Pause for human verification**: After completing all automated verification for a phase, pause and inform the human that the phase is ready for manual testing

### Pause Format

Use this format when pausing:

```
Phase [N] Complete - Ready for Manual Verification

Automated verification passed:
- [List automated checks that passed]

Please perform the manual verification steps listed in the plan:
- [List manual verification items from the plan]

Let me know when manual testing is complete so I can proceed to Phase [N+1].
```

### Important Notes on Pausing

- If instructed to execute multiple phases consecutively, skip the pause until the last phase
- Otherwise, assume you are just doing one phase
- Do not check off items in the manual testing steps until confirmed by the user

## Implementation Workflow

### 1. Read and Understand

- Read the entire plan file
- Read all referenced files (tickets, docs, code)
- Understand the current phase requirements
- Check what's already been completed (existing checkmarks)

### 2. Implement the Phase

- Follow the plan's guidance for this phase
- Make the required changes to files
- Adapt to reality while maintaining the plan's intent
- Update todos as you work

### 3. Verify Completion

**Automated Verification:**
- Run all automated verification commands
- Fix any failures before proceeding
- Common commands: `make test`, `make lint`, `make build`

**Manual Verification:**
- Present the list of manual verification steps
- Pause and wait for human confirmation
- Only proceed after receiving confirmation

### 4. Update the Plan

- Check off completed items in the plan using Edit
- Mark the phase as complete
- Do not check off manual items until human confirms

### 5. Move to Next Phase

- Only proceed to the next phase after:
  - All automated verification passes
  - Human confirms manual testing is complete
  - Current phase is fully checked off

## Resuming Work

If the plan has existing checkmarks:

- **Trust that completed work is done**
- **Pick up from the first unchecked item**
- **Verify previous work only if something seems off**

Don't re-implement what's already marked complete unless there's a specific reason.

## If You Get Stuck

When something isn't working as expected:

1. **Read and understand** all the relevant code first
2. **Consider if the codebase has evolved** since the plan was written
3. **Present the mismatch clearly** and ask for guidance
4. **Don't proceed** with uncertain implementation

### Using Sub-Tasks

Use sub-tasks sparingly - mainly for:
- Targeted debugging
- Exploring unfamiliar territory
- Researching specific issues

For most implementation work, work directly in the main context.

## Important Guidelines

1. **Follow intent, not just instructions**:
   - Understand WHY the plan calls for something
   - Adapt when reality doesn't match expectations
   - Maintain the end goal

2. **Verify as you go**:
   - Run tests frequently
   - Check that changes make sense
   - Don't accumulate unverified work

3. **Communicate issues early**:
   - Don't push through blockers
   - Present problems clearly
   - Get alignment before major adaptations

4. **Keep forward momentum**:
   - Complete phases fully
   - Don't get stuck in perfectionism
   - Remember the end goal

5. **Track progress visibly**:
   - Use TodoWrite
   - Update plan checkboxes
   - Mark phases complete

## Plan File Format

Expected plan structure:

```markdown
# Feature Implementation Plan

## Phase 1: Description

### Changes Required:
- [ ] Change 1
- [ ] Change 2

### Success Criteria:

#### Automated Verification:
- [ ] Tests pass: `make test`
- [ ] Linting passes: `make lint`

#### Manual Verification:
- [ ] Feature works in UI
- [ ] Performance is acceptable

---

## Phase 2: Description

[Similar structure...]
```

The plan should have:
- Clear phase boundaries
- Specific changes to make
- Automated verification steps
- Manual verification steps
- Checkboxes for tracking completion

## Example Workflow

```
User: Implement docs/plans/2025-10-27-add-auth.md