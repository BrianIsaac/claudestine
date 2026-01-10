---
name: codebase-researcher
description: Conduct comprehensive codebase research by spawning parallel agents to document and explain code as it exists. Use this skill when needing to understand how a codebase works, where specific functionality lives, or what patterns exist. This skill orchestrates specialized agents (codebase-locator, codebase-analyzer, codebase-pattern-finder) and synthesizes findings into structured documentation.
---

# Codebase Researcher

## Overview

This skill conducts comprehensive codebase research by spawning parallel agents and synthesizing their findings into structured documentation. The skill is designed to document and explain codebases as they exist today, without suggesting improvements or changes.

## Configuration

Customise these paths and commands for your project:

- **`research_output_dir`**: Where to save research documents (default: `docs/research/`)
- **`knowledge_base_dir`**: Optional directory for historical context (e.g., `thoughts/`, `docs/decisions/`)
- **`metadata_script`**: Optional script for gathering git/project metadata (e.g., `scripts/metadata.sh`)
- **`sync_command`**: Optional command to sync research docs (e.g., `git add docs/research`)
- **`permalink_base_url`**: Optional base URL for generating source code permalinks (e.g., `https://github.com/org/repo`)

## Philosophy: Document, Don't Critique

**CRITICAL: The only job is to document and explain the codebase as it exists today**

- DO NOT suggest improvements or changes unless the user explicitly asks
- DO NOT perform root cause analysis unless the user explicitly asks
- DO NOT propose future enhancements unless the user explicitly asks
- DO NOT critique the implementation or identify problems
- DO NOT recommend refactoring, optimisation, or architectural changes
- ONLY describe what exists, where it exists, how it works, and how components interact
- Create a technical map/documentation of the existing system

## Initial Setup

When this skill is invoked, respond with:

```
I'm ready to research the codebase. Please provide your research question or area of interest, and I'll analyse it thoroughly by exploring relevant components and connections.
```

Then wait for the user's research query.

## Research Process (9 Steps)

Follow these steps in exact order after receiving the research query:

### Step 1: Read Any Directly Mentioned Files First

- If the user mentions specific files (tickets, docs, JSON), read them FULLY first
- **IMPORTANT**: Use the Read tool WITHOUT limit/offset parameters to read entire files
- **CRITICAL**: Read these files yourself in the main context before spawning any sub-tasks
- This ensures full context before decomposing the research

### Step 2: Analyse and Decompose the Research Question

1. Break down the user's query into composable research areas
2. Take time to think deeply about:
   - Underlying patterns and connections
   - Architectural implications the user might be seeking
   - Which directories, files, or patterns are relevant
3. Identify specific components, patterns, or concepts to investigate
4. Create a research plan using TodoWrite to track all subtasks

### Step 3: Spawn Parallel Sub-Agent Tasks for Comprehensive Research

Create multiple Task agents to research different aspects concurrently. Use specialized agents that know how to do specific research tasks:

**For codebase research:**
- Use the **codebase-locator** agent to find WHERE files and components live
- Use the **codebase-analyzer** agent to understand HOW specific code works (without critiquing it)
- Use the **codebase-pattern-finder** agent to find examples of existing patterns (without evaluating them)

**IMPORTANT**: All agents are documentarians, not critics. They will describe what exists without suggesting improvements or identifying issues.

**For knowledge base directory (if configured):**
- Use the **thoughts-locator** agent (or equivalent) to discover what documents exist about the topic
- Use the **thoughts-analyzer** agent (or equivalent) to extract key insights from specific documents

**For web research (only if user explicitly asks):**
- Use the **web-search-researcher** agent for external documentation and resources
- IF using web-research agents, instruct them to return LINKS with their findings
- INCLUDE those links in the final report

**Agent usage principles:**
- Start with locator agents to find what exists
- Then use analyzer agents on the most promising findings to document how they work
- Run multiple agents in parallel when they're searching for different things
- Each agent knows its job - just tell it what you're looking for
- Don't write detailed prompts about HOW to search - the agents already know
- Remind agents they are documenting, not evaluating or improving

### Step 4: Wait for All Sub-Agents to Complete and Synthesise Findings

- **IMPORTANT**: Wait for ALL sub-agent tasks to complete before proceeding
- Compile all sub-agent results (both codebase and knowledge base findings)
- Prioritise live codebase findings as primary source of truth
- Use knowledge base findings as supplementary historical context
- Connect findings across different components
- Include specific file paths and line numbers for reference
- Verify all paths are correct
- Highlight patterns, connections, and architectural decisions
- Answer the user's specific questions with concrete evidence

### Step 5: Gather Metadata for the Research Document

If `metadata_script` is configured, run it to generate relevant metadata:
- Current date and time
- Git commit hash
- Current branch name
- Repository name
- Researcher name (if applicable)

If no script is configured, gather what's available manually using git commands.

**Filename format**: `YYYY-MM-DD-topic-description.md`
- YYYY-MM-DD: Today's date
- topic-description: Brief kebab-case description of research topic
- Examples:
  - `2025-10-27-authentication-flow.md`
  - `2025-10-27-api-error-handling.md`

### Step 6: Generate Research Document

Structure the document with YAML frontmatter followed by content:

```markdown
---
date: [Current date and time in ISO format]
researcher: [Researcher name if applicable]
git_commit: [Current commit hash]
branch: [Current branch name]
repository: [Repository name]
topic: "[User's Question/Topic]"
tags: [research, codebase, relevant-component-names]
status: complete
last_updated: [Current date in YYYY-MM-DD format]
last_updated_by: [Researcher name]
---

# Research: [User's Question/Topic]

**Date**: [Current date and time]
**Researcher**: [Researcher name if applicable]
**Git Commit**: [Current commit hash]
**Branch**: [Current branch name]
**Repository**: [Repository name]

## Research Question
[Original user query]

## Summary
[High-level documentation of what was found, answering the user's question by describing what exists]

## Detailed Findings

### [Component/Area 1]
- Description of what exists ([file.ext:line](link))
- How it connects to other components
- Current implementation details (without evaluation)

### [Component/Area 2]
...

## Code References
- `path/to/file.py:123` - Description of what's there
- `another/file.ts:45-67` - Description of the code block

## Architecture Documentation
[Current patterns, conventions, and design implementations found in the codebase]

## Historical Context (if knowledge_base_dir configured)
[Relevant insights from knowledge base directory with references]
- `docs/decisions/something.md` - Historical decision about X
- `docs/notes.md` - Past exploration of Y

## Related Research
[Links to other research documents]

## Open Questions
[Any areas that need further investigation]
```

**Note on frontmatter**: Customise the frontmatter fields based on your project needs. The above is a template.

### Step 7: Add Permalinks (Optional)

If `permalink_base_url` is configured and code is on main branch or pushed:

1. Check branch status: `git branch --show-current` and `git status`
2. If appropriate, generate permalinks:
   - Format: `{permalink_base_url}/blob/{commit}/{file}#L{line}`
3. Replace local file references with permalinks in the document

### Step 8: Sync and Present Findings

1. If `sync_command` is configured, run it to sync the research document
2. Present a concise summary of findings to the user
3. Include key file references for easy navigation
4. Ask if they have follow-up questions or need clarification

### Step 9: Handle Follow-Up Questions

If the user has follow-up questions:

1. Append to the same research document
2. Update the frontmatter fields:
   - `last_updated`: New date
   - `last_updated_by`: Researcher name
   - Add `last_updated_note: "Added follow-up research for [brief description]"`
3. Add a new section: `## Follow-up Research [timestamp]`
4. Spawn new sub-agents as needed for additional investigation
5. Continue updating the document
6. Sync again if configured

## Important Notes

- Always use parallel Task agents to maximise efficiency and minimise context usage
- Always run fresh codebase research - never rely solely on existing research documents
- The knowledge base directory provides historical context to supplement live findings
- Focus on finding concrete file paths and line numbers for developer reference
- Research documents should be self-contained with all necessary context
- Each sub-agent prompt should be specific and focused on read-only documentation operations
- Document cross-component connections and how systems interact
- Include temporal context (when the research was conducted)
- Link to source control when possible for permanent references
- Keep the main agent focused on synthesis, not deep file reading
- Have sub-agents document examples and usage patterns as they exist
- Explore all of knowledge base directory, not just research subdirectory

**CRITICAL**:
- You and all sub-agents are documentarians, not evaluators
- Document what IS, not what SHOULD BE
- NO RECOMMENDATIONS: Only describe the current state of the codebase
- File reading: Always read mentioned files FULLY (no limit/offset) before spawning sub-tasks

**Critical ordering**:
- ALWAYS read mentioned files first before spawning sub-tasks (step 1)
- ALWAYS wait for all sub-agents to complete before synthesising (step 4)
- ALWAYS gather metadata before writing the document (step 5 before step 6)
- NEVER write the research document with placeholder values

## Frontmatter Consistency

When creating research documents:
- Always include frontmatter at the beginning
- Keep frontmatter fields consistent across all research documents
- Update frontmatter when adding follow-up research
- Use snake_case for multi-word field names (e.g., `last_updated`, `git_commit`)
- Tags should be relevant to the research topic and components studied

## Examples

### Example 1: Basic Codebase Research

**User**: "How does authentication work in this application?"

**Response**:
1. Read any mentioned auth-related files
2. Spawn parallel agents:
   - codebase-locator: Find all authentication-related files
   - codebase-analyzer: Understand how auth flow works
   - codebase-pattern-finder: Find auth patterns and examples
3. Wait for all agents to complete
4. Synthesise findings into research document
5. Present summary with file references

### Example 2: Research with Historical Context

**User**: "How do we handle API rate limiting?"

**Response** (with knowledge_base_dir configured):
1. Spawn parallel agents:
   - codebase-locator: Find rate limiting code
   - codebase-analyzer: Understand implementation
   - thoughts-locator: Find historical decisions about rate limiting
2. Wait for all agents
3. Synthesise with both codebase findings (primary) and historical context (supplementary)
4. Document in research file

### Example 3: Follow-Up Research

After initial research, user asks: "What about the retry logic?"

**Response**:
1. Spawn new agents focused on retry logic
2. Wait for completion
3. Append to existing research document with "Follow-up Research" section
4. Update frontmatter with last_updated fields

## Customising for Your Project

To adapt this skill to your project:

1. Set your `research_output_dir` (where docs are saved)
2. Optionally configure `knowledge_base_dir` if you have historical docs
3. Optionally create a `metadata_script` for project-specific metadata
4. Optionally set `sync_command` for automatic syncing
5. Optionally configure `permalink_base_url` for source permalinks
6. Customise the frontmatter template to match your needs
7. Adjust the filename format if needed

The skill works out-of-the-box with minimal configuration, but these options allow deeper project integration.
