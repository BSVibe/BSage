---
name: testing-standards
description: Testing guidelines and coverage standards for BSage
---

# Testing Standards Skill

## Test Structure

```
bsage/
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_skill_loader.py
    ├── test_skill_runner.py
    ├── test_skill_context.py
    ├── test_agent_loop.py
    ├── test_scheduler.py
    ├── test_safe_mode.py
    ├── test_connector_manager.py
    ├── test_garden_writer.py
    └── test_vault.py

tests/
└── fixtures/
    ├── sample_skill/
    │   ├── skill.yaml
    │   └── skill.py
    └── sample_vault/
        ├── seeds/
        └── garden/
```

## Test Types

### Unit Tests

**Purpose**: Test individual functions/classes with mocked dependencies

**Example — SkillLoader**:
```python
# bsage/tests/test_skill_loader.py
import pytest
from pathlib import Path
from bsage.core.skill_loader import SkillLoader, SkillMeta

@pytest.mark.asyncio
async def test_load_all_discovers_skills(tmp_path):
    skill_dir = tmp_path / "garden-writer"
    skill_dir.mkdir()
    (skill_dir / "skill.yaml").write_text(
        "name: garden-writer\nversion: 1.0.0\ncategory: process\n"
        "is_dangerous: false\ndescription: Test\n"
    )
    loader = SkillLoader(tmp_path)
    registry = await loader.load_all()
    assert "garden-writer" in registry
    assert isinstance(registry["garden-writer"], SkillMeta)

@pytest.mark.asyncio
async def test_load_all_skips_invalid_yaml(tmp_path):
    skill_dir = tmp_path / "bad-skill"
    skill_dir.mkdir()
    # No skill.yaml
    loader = SkillLoader(tmp_path)
    registry = await loader.load_all()
    assert "bad-skill" not in registry

def test_skill_meta_required_fields():
    from bsage.core.exceptions import SkillLoadError
    with pytest.raises((TypeError, SkillLoadError)):
        SkillMeta(name="test")  # Missing required fields
```

**Coverage target**: 80%+

---

### Mock Patterns

#### Mock SkillContext

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_context():
    context = MagicMock()
    context.logger = MagicMock()
    context.connector = MagicMock(return_value=AsyncMock())
    context.garden = AsyncMock()
    context.garden.write_seed = AsyncMock()
    context.garden.write_garden = AsyncMock()
    context.garden.write_action = AsyncMock()
    context.garden.read_notes = AsyncMock(return_value=[])
    context.llm = AsyncMock()
    context.llm.chat = AsyncMock(return_value="LLM response")
    context.config = {}
    context.input_data = None
    return context
```

#### Mock Claude API

```python
import pytest
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_claude():
    with patch("bsage.core.skill_runner.anthropic.Anthropic") as mock:
        instance = mock.return_value
        instance.messages.create.return_value = MagicMock(
            content=[MagicMock(text="Processed result")],
            usage=MagicMock(input_tokens=500, output_tokens=100),
        )
        yield mock

def test_llm_summarize(mock_claude):
    # Test that LLM integration works with mocked client
    pass
```

#### Mock Connector

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_calendar_connector():
    connector = AsyncMock()
    connector.authenticate = AsyncMock()
    connector.fetch_events = AsyncMock(return_value=[
        {"summary": "Meeting", "start": "2026-02-22T10:00:00"},
        {"summary": "Lunch", "start": "2026-02-22T12:00:00"},
    ])
    return connector

@pytest.fixture
def mock_connector_manager(mock_calendar_connector):
    manager = MagicMock()
    manager.get = AsyncMock(return_value=mock_calendar_connector)
    return manager
```

#### Mock APScheduler

```python
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_scheduler():
    with patch("bsage.core.scheduler.AsyncIOScheduler") as mock:
        instance = mock.return_value
        instance.add_job = MagicMock()
        instance.start = MagicMock()
        instance.get_jobs = MagicMock(return_value=[])
        yield instance
```

#### Mock GardenWriter (File System)

```python
@pytest.fixture
def mock_garden_writer(tmp_path):
    """Use tmp_path for actual file system tests."""
    from bsage.garden.writer import GardenWriter
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "seeds").mkdir()
    (vault_path / "garden").mkdir()
    (vault_path / "actions").mkdir()
    return GardenWriter(vault_path)
```

---

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

**Note**: Add to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

---

### Test Fixtures (files)

```python
# tests/fixtures/ contains:
# - sample_skill/skill.yaml  (valid skill metadata)
# - sample_skill/skill.py    (simple execute function)
# - sample_vault/            (minimal vault structure)

@pytest.fixture
def sample_skill_dir():
    return Path("tests/fixtures/sample_skill")

@pytest.fixture
def sample_vault_dir():
    return Path("tests/fixtures/sample_vault")
```

---

## Coverage Requirements

**Minimum coverage by module**:
- `core/` (config, exceptions, skill_loader): 90%
- `core/` (agent_loop, scheduler, safe_mode): 80%
- `connectors/` (base, manager): 80%
- `garden/` (writer, vault): 85%
- `interface/`: 75%

**Check coverage**:
```bash
pytest bsage/tests/ --cov=bsage --cov-report=html
open htmlcov/index.html
```

---

## Critical Testing Rules

1. **Never call real APIs in tests** (Claude, Connectors, APScheduler triggers)
2. **Always mock external services** with `unittest.mock.patch`
3. **Test error paths** alongside happy paths
4. **Use `tmp_path` pytest fixture** for temporary test files and vault
5. **Clean up after tests** (pytest handles `tmp_path` cleanup automatically)
6. **Use `asyncio_mode = "auto"`** to avoid `@pytest.mark.asyncio` on every test
7. **Test SafeModeGuard** — verify is_dangerous skills are blocked without approval
8. **Test Vault boundary** — verify data doesn't leak outside vault_path
