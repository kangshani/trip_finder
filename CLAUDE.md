# Claude Code Skills — Condensed Spec


Skills extend Claude's capabilities via `SKILL.md` files. Claude loads them automatically when relevant, or users invoke them with `/skill-name`.


## File Structure


```
.claude/skills/<skill-name>/
├── SKILL.md           # Instructions (required)
├── template.md        # Optional template
├── examples/          # Optional examples
└── scripts/           # Optional scripts Claude can execute
```


## Skill Locations (priority order)


| Level      | Path                                         | Scope                        |
|------------|----------------------------------------------|------------------------------|
| Enterprise | Managed settings                             | All org users                |
| Personal   | `~/.claude/skills/<name>/SKILL.md`           | All your projects            |
| Project    | `.claude/skills/<name>/SKILL.md`             | This project only            |
| Plugin     | `<plugin>/skills/<name>/SKILL.md`            | Where plugin is enabled      |


Higher priority wins on name conflicts. Plugin skills use `plugin:skill` namespace (no conflicts). Files in `.claude/commands/` still work; skills take precedence on name collision.


Nested `.claude/skills/` directories are auto-discovered (e.g. `packages/frontend/.claude/skills/`). Skills from `--add-dir` directories are also loaded.


## SKILL.md Format


```yaml
---
name: my-skill              # Optional. Defaults to directory name. Lowercase/numbers/hyphens, max 64 chars.
description: What it does    # Recommended. Claude uses this to decide when to auto-load.
argument-hint: [issue-num]   # Optional. Shown in autocomplete.
disable-model-invocation: true  # Optional. Prevents Claude from auto-invoking. Default: false.
user-invocable: false        # Optional. Hides from / menu. Default: true.
allowed-tools: Read, Grep    # Optional. Tools allowed without permission prompts when skill is active.
model: claude-opus-4-6       # Optional. Model override when skill is active.
context: fork                # Optional. Runs in isolated subagent context.
agent: Explore               # Optional. Subagent type when context: fork. Default: general-purpose.
hooks: ...                   # Optional. Lifecycle hooks scoped to this skill.
---


Markdown instructions here. Claude follows these when the skill is invoked.
```


## Invocation Control


| Setting                          | User can invoke | Claude can invoke | Context behavior                                   |
|----------------------------------|-----------------|-------------------|----------------------------------------------------|
| (defaults)                       | Yes             | Yes               | Description always loaded; full content on invoke   |
| `disable-model-invocation: true` | Yes             | No                | Description not loaded; full content on user invoke |
| `user-invocable: false`          | No              | Yes               | Description always loaded; full content on invoke   |


## String Substitutions


| Variable               | Description                                          |
|------------------------|------------------------------------------------------|
| `$ARGUMENTS`           | All args passed to skill. Auto-appended if not used. |
| `$ARGUMENTS[N]` / `$N` | Nth argument (0-based).                             |
| `${CLAUDE_SESSION_ID}` | Current session ID.                                  |


Example:
```yaml
---
name: migrate-component
---
Migrate $0 from $1 to $2. Preserve all behavior and tests.
```
`/migrate-component SearchBar React Vue` → `Migrate SearchBar from React to Vue.`


## Dynamic Context Injection


`` !`command` `` runs a shell command before the skill content is sent to Claude. Output replaces the placeholder.


```yaml
---
name: pr-summary
context: fork
agent: Explore
---
PR diff: !`gh pr diff`
Changed files: !`gh pr diff --name-only`


Summarize this pull request.
```


Commands execute as preprocessing — Claude only sees the output.


## Subagent Execution (context: fork)


`context: fork` runs the skill in an isolated subagent. The skill content becomes the subagent's task prompt. No access to conversation history.


The `agent` field picks the execution environment: built-in (`Explore`, `Plan`, `general-purpose`) or custom (`.claude/agents/`). Default: `general-purpose`.


| Approach                   | System prompt              | Task              | Also loads         |
|----------------------------|----------------------------|--------------------|--------------------|
| Skill with `context: fork` | From agent type            | SKILL.md content   | CLAUDE.md          |
| Subagent with `skills`     | Subagent's markdown body   | Delegation message | Preloaded skills   |


Only use `context: fork` for skills with explicit tasks — guidelines-only skills have no actionable prompt for the subagent.


## Permissions


**Deny all skills:** Add `Skill` to deny rules in `/permissions`.


**Allow/deny specific skills:**
```
Skill(commit)          # exact match
Skill(review-pr *)     # prefix match
```


**Per-skill tool restrictions:** `allowed-tools` in frontmatter grants tool access without per-use approval when the skill is active. Base permission settings still govern other tools.


## Bundled Skills


- `/simplify` — Reviews recent changes for reuse/quality/efficiency, spawns 3 parallel review agents, applies fixes. Pass text to focus: `/simplify focus on memory efficiency`.
- `/batch <instruction>` — Orchestrates large-scale parallel changes. Decomposes work into 5-30 units, spawns one agent per unit in isolated git worktrees, each opens a PR. Requires git repo. Example: `/batch migrate src/ from Solid to React`.
- `/debug [description]` — Troubleshoots current session by reading debug logs.


## Supporting Files


Keep `SKILL.md` under 500 lines. Move detailed docs to separate files and reference them:


```markdown
## Resources
- API details: [reference.md](reference.md)
- Examples: [examples.md](examples.md)
```


Claude loads supporting files on demand, not every invocation.


## Two Types of Skill Content


**Reference skills** — knowledge Claude applies to current work (conventions, patterns, style guides). Runs inline alongside conversation.


```yaml
---
name: api-conventions
description: API design patterns for this codebase
---
Use RESTful naming. Return consistent error formats. Include request validation.
```


**Task skills** — step-by-step instructions for specific actions. Often `disable-model-invocation: true`.


```yaml
---
name: deploy
description: Deploy to production
context: fork
disable-model-invocation: true
---
1. Run test suite
2. Build application
3. Push to deployment target
```


## Extended Thinking


Include the word "ultrathink" anywhere in skill content to enable extended thinking.


## Context Budget


Skill descriptions are loaded into context (2% of context window, fallback 16K chars). If many skills exceed the budget, some are excluded. Check with `/context`. Override with `SLASH_COMMAND_TOOL_CHAR_BUDGET` env var.


## Troubleshooting


- **Skill not triggering:** Check description keywords match natural language. Verify with "What skills are available?" Try `/skill-name` directly.
- **Triggers too often:** Make description more specific, or add `disable-model-invocation: true`.
- **Claude doesn't see all skills:** Context budget exceeded. Run `/context` to check.


## Self-Annealing (Default Behavior)


Skills self-heal. When a skill runs and produces an error — wrong API endpoint, missing parameter, bad auth, incorrect model ID, flawed logic — the agent must automatically patch the SKILL.md (and/or its supporting files/scripts) so the same failure cannot recur. This is not optional; it is the default way skills work.


### How it works


1. **Run the skill.** Execute normally.
2. **Error occurs.** Any failure: script crash, API error, wrong output format, missing dependency, auth failure, etc.
3. **Fix the immediate problem.** Resolve the error so the current run succeeds.
4. **Patch the skill.** Immediately update `SKILL.md`, supporting docs, or scripts with the fix. The goal: if the skill runs again tomorrow with zero context, the same error is impossible.
5. **Resume.** Continue the original task.


### What to patch


- **Wrong values** (API endpoints, model IDs, auth headers, config paths) → correct them in the skill.
- **Missing steps** (forgot to install a dep, missing auth check, missing env var) → add the step to the skill instructions.
- **Flawed logic in scripts** (bad parsing, wrong API call sequence, missing error handling at system boundaries) → fix the script and add a comment noting why.
- **Incorrect assumptions** (file paths, data formats, service behavior) → update the skill to document the actual behavior.


### What NOT to patch


- One-off environmental issues (network timeout, rate limit, disk full). These aren't skill bugs.
- User input errors. The skill shouldn't try to anticipate every possible bad input.


### Example


A skill calls the Anthropic API with `model: "claude-opus-4-5-20251101"`. The API rejects it — the correct ID is `claude-opus-4-6`. The agent should:
1. Fix the script to use `claude-opus-4-6`
2. Update the SKILL.md (or relevant docs) noting the correct model ID
3. Continue the original task


The principle: **every error is a lesson the skill learns permanently.** Skills get more reliable with each run, converging toward zero-failure execution.


## Quick Reference: Minimal Skill


```yaml
---
description: Does X when Y
---
Instructions for Claude.
```


That's it. `name` defaults to directory name. Everything else is optional.

