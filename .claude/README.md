# Claude Code Configuration

BSage Claude Code setup for development workflow.

## Structure

```
.claude/
├── README.md           # This file
├── skills/             # Reusable patterns and standards
│   ├── project-structure.md
│   ├── testing-standards.md
│   └── core-patterns.md
├── rules/              # Always-follow guidelines (enforced)
│   ├── architecture.md
│   ├── skill-system.md
│   ├── testing.md
│   └── security.md
├── commands/           # Slash commands for quick actions
│   ├── test.md
│   ├── skill.md
│   └── deploy.md
└── contexts/           # Mode-specific prompts
    ├── worker.md
    ├── review.md
    └── debug.md
```

## Skills

**Reusable implementation patterns** that can be referenced when needed.

- **project-structure.md**: Folder hierarchy, naming conventions
- **testing-standards.md**: Test requirements and patterns
- **core-patterns.md**: Core Engine patterns (SkillLoader, SkillRunner, AgentLoop, GardenWriter, Scheduler)

**Usage**: Reference in implementation (e.g., "See `.claude/skills/core-patterns.md`")

## Rules

**Always-enforced guidelines** that must be followed in all code.

- **architecture.md**: Core architectural decisions (uv, pydantic-settings, structlog, async, dataclasses)
- **skill-system.md**: Skill system rules (skill.yaml, execute(context), is_dangerous, Connector access)
- **testing.md**: All code MUST have tests (>=80% coverage)
- **security.md**: Security requirements (no hardcoded credentials, Safe mode, Vault data boundary)

**Enforcement**: Claude will check these before proceeding with implementation.

## Commands

**Slash commands** for common operations.

- `/test [module]`: Run tests with coverage
- `/skill <category>/<name>`: Create new Skill with boilerplate
- `/deploy`: Verify BSage readiness and Vault integration

**Usage**: Type `/test` in Claude Code to run tests.

## Contexts

**Mode-specific prompts** for different work types.

- **worker.md**: Implementation mode (building Core Engine, Skills, Connectors)
- **review.md**: Code review mode (verifying quality)
- **debug.md**: Debugging mode (diagnosing issues)

**Usage**: Activated automatically based on task context.

## Quick Reference

### Starting Implementation

1. Review the plan in `.claude/plans/` if it exists
2. Reference `.claude/skills/` for patterns
3. Follow `.claude/rules/` strictly
4. Use `/skill` to generate Skill boilerplate
5. Implement with tests
6. Verify with `/deploy`

### Code Review

1. Run automated checks (`.claude/contexts/review.md`)
2. Verify against `.claude/rules/`
3. Check test coverage (`/test`)
4. Approve or request changes

### Debugging

1. Collect logs and error messages
2. Follow `.claude/contexts/debug.md`
3. Use debugging tools (pdb, structlog)
4. Add test to prevent regression

## Integration with Development

### Worker Session

When implementing:
```bash
# 1. Install dependencies
uv pip install -e ".[dev]"

# 2. Generate Skill scaffold
/skill process/garden-writer

# 3. Implement
# (Follow .claude/skills/ patterns)

# 4. Test
/test bsage

# 5. Verify
/deploy
```

### QA Session

When reviewing:
```bash
# 1. Check compliance
# (Follow .claude/contexts/review.md)

# 2. Run tests
/test

# 3. Security audit
grep -r "sk-ant-\|from bsage" skills/

# 4. Approve or reject
```

## Customization

This configuration is tailored for BSage. Modify as needed:

- Add new skills for emerging patterns
- Update rules if architecture changes
- Create new commands for frequent operations
- Add contexts for new work modes

## Philosophy

1. **Consistency**: Follow established patterns
2. **Quality**: Never skip tests or security checks
3. **Speed**: Use commands to avoid repetitive work
4. **Documentation**: Skills are living documentation
