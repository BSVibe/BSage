---
name: project-structure
description: BSage project folder structure and naming conventions
---

# Project Structure Skill

## Root Structure

```
BSage/
├── .env                          # Secrets (gitignored)
├── .env.example                  # Template (committed)
├── .gitignore
├── pyproject.toml                # uv-based, CLI entry point
├── bsage/
│   ├── __init__.py
│   ├── cli.py                    # Click CLI (bsage command)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             # pydantic-settings Settings
│   │   ├── logging.py            # structlog configuration
│   │   ├── exceptions.py         # Domain exception classes
│   │   ├── credential_store.py   # JSON 기반 credential 관리
│   │   ├── skill_loader.py       # skills/ 스캔 → yaml 파싱 → 레지스트리
│   │   ├── skill_runner.py       # context 주입 → execute() 호출
│   │   ├── skill_context.py      # Skill에 주입되는 context 객체
│   │   ├── agent_loop.py         # InputSkill → ProcessSkill 체인 결정
│   │   ├── scheduler.py          # APScheduler 기반 trigger 관리
│   │   └── safe_mode.py          # SafeModeGuard (is_dangerous 체크)
│   ├── garden/
│   │   ├── __init__.py
│   │   ├── writer.py             # GardenWriter (seeds/garden/actions 쓰기)
│   │   ├── vault.py              # Vault 경로 관리, 읽기
│   │   └── sync.py               # SyncManager (OutputSkill 동기화)
│   ├── gateway/
│   │   ├── __init__.py
│   │   ├── app.py                # FastAPI factory
│   │   ├── dependencies.py       # AppState 초기화
│   │   ├── routes.py             # HTTP REST API
│   │   └── ws.py                 # WebSocket 관리
│   ├── interface/
│   │   ├── __init__.py
│   │   └── cli_interface.py      # CLI 기반 SafeMode 승인 등
│   └── tests/
│       ├── __init__.py
│       ├── test_config.py
│       ├── test_credential_store.py
│       ├── test_skill_loader.py
│       ├── test_skill_runner.py
│       ├── test_skill_context.py
│       ├── test_agent_loop.py
│       ├── test_scheduler.py
│       ├── test_safe_mode.py
│       ├── test_garden_writer.py
│       └── test_vault.py
├── skills/                       # 설치된 Skill 디렉토리
│   ├── garden-writer/
│   │   ├── skill.yaml
│   │   └── skill.py
│   ├── insight-linker/
│   │   └── skill.yaml            # yaml only (LLM 기반)
│   └── ...
├── tests/                        # Root-level test fixtures
│   └── fixtures/
│       ├── sample_skill/
│       │   ├── skill.yaml
│       │   └── skill.py
│       └── sample_vault/
│           ├── seeds/
│           ├── garden/
│           └── actions/
├── vault/                        # Obsidian Vault (gitignored or 별도 관리)
│   ├── seeds/                    # InputSkill이 수집한 원시 데이터
│   │   ├── conversations/
│   │   ├── calendar/
│   │   └── email/
│   ├── garden/                   # ProcessSkill이 정리한 지식
│   │   ├── ideas/
│   │   ├── projects/
│   │   └── insights/
│   ├── actions/                  # 에이전트 행동 로그
│   │   └── 2026-02-22.md
│   └── skills/                   # 설치된 Skill 목록
│       └── installed.md
└── tmp/                          # Temporary files (gitignored)
```

## Key Dataclasses

### `core/skill_loader.py`

```python
@dataclass
class SkillMeta:
    name: str
    version: str
    category: str              # input / process / output / meta
    is_dangerous: bool
    description: str
    author: str = ""
    entrypoint: str | None = None
    trigger: dict | None = None
    rules: list[str] = field(default_factory=list)
```

### `core/skill_context.py`

```python
@dataclass
class SkillContext:
    credentials: CredentialStore     # context.credentials.get("name")
    garden: GardenWriter             # context.garden.write_seed(...)
    llm: LLMClient                   # context.llm.chat(...)
    config: dict                     # Skill-specific config
    logger: BoundLogger              # structlog logger
    input_data: dict | None = None   # InputSkill 결과 (ProcessSkill용)
```

### `garden/writer.py`

```python
@dataclass
class GardenNote:
    title: str
    content: str
    note_type: str                   # seed / idea / project / insight
    source: str                      # Skill 이름
    related: list[str] = field(default_factory=list)  # wikilinks
    tags: list[str] = field(default_factory=list)
```

### `core/safe_mode.py`

```python
@dataclass
class ApprovalRequest:
    skill_name: str
    description: str
    action_summary: str
```

## Naming Conventions

**Python**:
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions: `snake_case()`
- Constants: `UPPER_SNAKE_CASE`

**Skill directories**:
- Pattern: `kebab-case` (e.g., `garden-writer`, `calendar-input`)

**Vault notes**:
- Pattern: `{YYYY-MM-DD}_{slug}.md` or `{YYYY-MM-DD}.md` (actions)

**Directories**:
- All lowercase: `bsage/`, `skills/`, `vault/`, `tmp/`

## Import Order

**Python**:
```python
# 1. Standard library
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field

# 2. Third-party
import structlog
import yaml
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# 3. Local application
from bsage.core.config import settings
from bsage.core.exceptions import SkillLoadError
```

## Critical Rules

1. **All paths from settings**:
   - `settings.vault_path` for Vault
   - `settings.skills_dir` for Skills
   - `settings.tmp_dir` for temporary files
   - `settings.credentials_dir` for credentials

2. **Never share code between modules via direct import of implementation** (only via dataclasses/return values)

3. **Skill definitions ONLY in `skill.yaml`** — no hardcoded configuration

4. **Credentials location**: `.credentials/` directory (gitignored), managed by `CredentialStore`

5. **Each module is independently testable** via mocks

6. **Vault data never leaves Vault** — except via explicit OutputSkill
