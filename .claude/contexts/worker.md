---
context: worker
description: Implementation mode - building BSage Core Engine and Skills
---

# Worker Context

You are implementing BSage — a personal AI agent that records everything about the user in a 2nd Brain (Obsidian Vault) and proactively acts on that knowledge. A transparent, safe alternative to OpenClaw.

## Current Phase

Phase 1: Core Engine

**Goal**: Skill trigger → AgentLoop → ProcessSkill chain → GardenWriter → Vault

**Architecture**:
```
Scheduler (cron/webhook/event)
        ↓
InputSkill.execute(context)
        ↓
AgentLoop.on_input(raw_data)
        ↓
GardenWriter → /seeds 저장
        ↓
rules 확인 or LLM 판단 → ProcessSkill 목록 결정
        ↓
SafeModeGuard.check()
        ↓ (승인)
ProcessSkill.execute(context)
        ↓
GardenWriter → /garden + /actions 저장
        ↓
OutputSkill → Vault 동기화
```

## Your Role

1. **Implement modules** per the plan
2. **Write tests** alongside code (80%+ coverage)
3. **Follow standards** in `.claude/skills/`
4. **Ask questions** when requirements unclear

## Before You Start

Read:
- `.claude/skills/project-structure.md` - directory layout
- `.claude/skills/core-patterns.md` - Core Engine patterns
- `.claude/rules/skill-system.md` - Skill system rules
- Relevant rules in `.claude/rules/`

## Implementation Pattern

1. **Read existing code** in related modules first
2. **Define dataclasses** for input/output types
3. **Implement async functions** with type hints
4. **Write unit tests** with mocked dependencies
5. **Verify with** `/test bsage`

## Critical Rules

Always follow `.claude/rules/`:
- **Skill system** — skill.yaml, execute(context), is_dangerous
- **pydantic-settings** — all config from environment variables
- **structlog** — structured JSON logging throughout
- **Type hints** required on all public functions
- **Tests required** (80%+ coverage)
- **Skill definitions in skill.yaml** — never hardcode
- **Dataclasses** for structured data (not dicts)
- **Vault data boundary** — data never leaves Vault
- **SafeModeGuard** — never bypass is_dangerous check

## Code Quality

Before committing:
- [ ] Type hints on all public functions
- [ ] Tests written and passing (>= 80% coverage)
- [ ] External APIs mocked (Claude, Connectors, APScheduler)
- [ ] structlog used (not print or logging.info)
- [ ] No hardcoded credentials
- [ ] Skill definitions in skill.yaml
- [ ] SafeModeGuard properly integrated

## Reference Documents

- `.claude/skills/project-structure.md`: Directory layout
- `.claude/skills/core-patterns.md`: Core Engine data flow
- `.claude/skills/testing-standards.md`: Test patterns

## Communication

- **Progress**: Update todos
- **Blockers**: Ask questions immediately
- **Decisions**: Document in code comments
- **Completion**: Run `/deploy` checklist
