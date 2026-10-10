# Secretary Development Workflow

> Full integrated lifecycle: Idea → Ship → Retro
> Tools: gstack + oh-my-agents

## Lifecycle Phases

| Phase | Command | Purpose |
|-------|---------|---------|
| Ideate | `/office-hours` | Product diagnostic, design doc |
| Plan | `/plan-ceo-review` | Strategy & scope review |
| Plan | `/plan-eng-review` | Architecture & eng review |
| Plan | `/plan-design-review` | Design & UX review |
| Decompose | `/spec-to-task` | Layer-aware execution plan |
| Execute | develop + hooks | Implement with automatic enforcement |
| Verify | `/verify` | Build, test, lint, arch check |
| Review | `/review` | PR structural review (SQL, LLM safety) |
| Review | `/harness-review` | Four-pillar harness review |
| Ship | `/ship` | Version, changelog, PR |
| Docs | `/document-release` | Post-ship doc sync |
| Retro | `/retro` + `/harness-dashboard` | Eng metrics + harness health |
| Guard | `/encode-mistake` | Convert failures to rules |
| Sweep | `/entropy-sweep` | Weekly codebase health scan |

## Research → Plan → Execute → Verify

Every non-trivial task follows this cycle:

### 1. Research
- Read relevant code and documentation
- Use subagents for parallel exploration
- Check `docs/exec-plans/` for related prior work

### 2. Plan
- For 3+ step tasks or architecture decisions: enter plan mode
- Write plan to `tasks/todo.md` with checkable items
- Get plan confirmed before implementing
- For major features: create execution plan in `docs/exec-plans/active/`

### 3. Execute
- Follow the plan step by step
- Track progress in `tasks/todo.md`
- Use TDD: write tests first, then implement
- Commit atomically per logical change

### 4. Verify
- Run `cd backend && pytest` (backend tests)
- Run `cd mobile && flutter test` (mobile tests)
- Run `cd backend && alembic upgrade head` (migration check)
- Diff against main: `git diff main...HEAD`
- Ask: "Would a staff engineer approve this?"

## Task Management

1. Write plan to `tasks/todo.md` with checkable items
2. Confirm plan before implementing
3. Mark items complete as you go
4. Add review section when done
5. Record lessons in `tasks/lessons.md` when corrected

## Agent Workflow Principles

- **Plan First**: Non-trivial tasks must start with a plan
- **Subagent Strategy**: Offload research/exploration to subagents, keep main context clean
- **Self-Improvement**: Record corrections in `tasks/lessons.md`, write rules to prevent recurrence
- **Verify Before Done**: Never mark complete without proof (tests pass, logs clean, diff reviewed)
- **Pursue Elegance (moderately)**: Pause to consider cleaner approaches, but don't over-engineer
- **Fix Bugs Autonomously**: On bug report → locate → fix → verify. Zero user context switching.

## Core Principles

- **Simplicity First**: Each change as simple as possible, minimal code impact
- **No Shortcuts**: Find root cause, don't patch. Senior developer standard.
- **Minimal Blast Radius**: Only change what's necessary, avoid introducing new bugs
