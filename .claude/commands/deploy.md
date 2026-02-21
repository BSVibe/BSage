---
name: deploy
description: BSage CLI readiness and Vault integration verification checklist
---

# Deploy Command

Verify BSage is ready for use.

## Usage

```
/deploy
```

## Verification Checklist

### 1. Implementation Complete

- [ ] Core Engine modules implemented (SkillLoader, SkillRunner, AgentLoop, Scheduler, SafeModeGuard)
- [ ] `bsage` CLI entry point works
- [ ] All sub-commands functional (`run`, `skill list`, `skill install`, `connector list`, `status`)
- [ ] Logging configured (structlog JSON)
- [ ] Error handling for all core components

**Check:**
```bash
# Verify CLI entry point
bsage --help

# Check all sub-commands exist
bsage run --help
bsage skill list --help
bsage skill install --help
bsage connector list --help
bsage status --help
```

### 2. Testing

- [ ] Unit tests (>= 80% coverage)
- [ ] External APIs mocked (Claude, Connectors, APScheduler)
- [ ] Error cases tested
- [ ] All tests passing

**Check:**
```bash
pytest bsage/tests/ --cov=bsage --cov-fail-under=80
```

### 3. Configuration

- [ ] `.env.example` provided with all required variables
- [ ] No hardcoded credentials
- [ ] `pyproject.toml` with correct CLI script entry point
- [ ] All dependencies listed in pyproject.toml

**Check:**
```bash
# Verify .env.example exists and is complete
cat .env.example

# Verify no hardcoded secrets
grep -r "sk-ant-" bsage/ | grep -v ".env\|test"

# Verify CLI entry point
grep 'scripts' pyproject.toml
```

### 4. Security

- [ ] All credentials from environment variables
- [ ] `.credentials/` in `.gitignore`
- [ ] No credentials in logs
- [ ] SafeModeGuard correctly blocks is_dangerous Skills
- [ ] Vault path traversal prevention working

**Check:**
```bash
# Check gitignore
grep ".credentials\|.env\|vault/" .gitignore

# Verify no hardcoded credentials
grep -r "password\s*=\s*\"" bsage/ | grep -v test
```

### 5. End-to-End Verification

**Step 1**: Skill loading
```bash
bsage skill list
# Expected: Table of installed skills with category, version, status
```

**Step 2**: Vault connection
```bash
bsage status
# Expected: Vault path accessible, skills loaded, connectors listed
```

**Step 3**: Safe mode test
```bash
bsage run --skill calendar-writer --dry-run
# Expected: SafeModeGuard prompts for approval (is_dangerous=true)
```

**Step 4**: Garden writing test
```bash
bsage run --skill garden-writer --input "test data"
# Expected: Markdown note created in vault/garden/
```

**Step 5**: Verify Vault output
```bash
ls $VAULT_PATH/garden/**/*.md | head -5
# Expected: Properly formatted notes with frontmatter
cat $VAULT_PATH/actions/$(date +%Y-%m-%d).md
# Expected: Action log entries with timestamps
```

### 6. Output Quality

- [ ] YAML frontmatter correctly formatted on all notes
- [ ] seeds/garden/actions directory structure correct
- [ ] Obsidian-compatible wikilinks (`[[note-name]]`)
- [ ] Action logs have timestamps and skill names

## Example Output

```bash
$ /deploy

Verifying BSage readiness...

OK CLI
  OK bsage CLI available
  OK All sub-commands registered

OK Testing
  OK Coverage: 85% (threshold: 80%)
  OK All tests passing (38 passed)
  OK External APIs mocked

OK Configuration
  OK .env.example complete (6 variables)
  OK No hardcoded credentials
  OK pyproject.toml scripts registered

OK Security
  OK .credentials/ in .gitignore
  OK SafeModeGuard active
  OK Vault path traversal blocked

E2E Verification:
  OK skill list: 8 skills loaded
  OK status: Vault connected, 2 connectors active
  OK Safe mode: is_dangerous skill blocked without approval
  OK garden-writer: Note created successfully

Summary: All checks passed. Ready to use!
```
