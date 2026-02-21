---
name: skill
description: Create a new BSage Skill with standard boilerplate
---

# Skill Command

Generate a new Skill with standard structure and boilerplate.

## Usage

```
/skill <category>/<skill-name>
```

## Example

```
/skill input/calendar-input
/skill process/garden-writer
/skill output/git-output
/skill meta/skill-builder
```

## What This Does

1. **Creates skill directory** at `skills/<skill-name>/`
2. **Generates skill.yaml** with category-appropriate defaults
3. **Generates skill.py** with `execute(context)` boilerplate
4. **Creates test file** at `bsage/tests/test_skill_<name>.py`

## Generated Structure

For `/skill input/calendar-input`:

```
skills/
└── calendar-input/
    ├── skill.yaml      # Metadata + trigger config
    └── skill.py         # execute(context) function

bsage/
└── tests/
    └── test_skill_calendar_input.py
```

## Generated Files

### skills/calendar-input/skill.yaml

```yaml
name: calendar-input
version: 1.0.0
author: bslab
category: input
is_dangerous: false
requires_connector: google-calendar
entrypoint: skill.py::execute
trigger:
  type: cron
  schedule: "*/15 * * * *"
rules:
  - garden-writer
description: Google Calendar 일정을 2nd Brain으로 수집
```

### skills/calendar-input/skill.py

```python
from __future__ import annotations


async def execute(context):
    """Google Calendar 일정을 수집하여 seed로 저장."""
    context.logger.info("calendar_input_start")

    cal = context.connector("google-calendar")
    events = await cal.fetch_events()

    await context.garden.write_seed("calendar", {"events": events})

    context.logger.info("calendar_input_complete", event_count=len(events))
    return {"collected": len(events)}
```

### bsage/tests/test_skill_calendar_input.py

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
    return context


@pytest.mark.asyncio
async def test_execute_collects_events(mock_context):
    mock_context.connector.return_value.fetch_events = AsyncMock(
        return_value=[{"summary": "Meeting", "start": "2026-02-22T10:00:00"}]
    )

    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("skill", "skills/calendar-input/skill.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    result = await module.execute(mock_context)

    assert result["collected"] == 1
    mock_context.garden.write_seed.assert_called_once()


@pytest.mark.asyncio
async def test_execute_handles_empty_calendar(mock_context):
    mock_context.connector.return_value.fetch_events = AsyncMock(return_value=[])

    from importlib.util import spec_from_file_location, module_from_spec
    spec = spec_from_file_location("skill", "skills/calendar-input/skill.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)

    result = await module.execute(mock_context)

    assert result["collected"] == 0
```

## Category Templates

### InputSkill

```yaml
category: input
trigger:
  type: cron
  schedule: "*/15 * * * *"
rules:
  - garden-writer
```

### ProcessSkill

```yaml
category: process
is_dangerous: false    # true if external side effects
```

### OutputSkill

```yaml
category: output
requires_connector: null  # or specific output target
```

### MetaSkill

```yaml
category: meta
is_dangerous: false
```

## Next Steps

After generation:

1. **Fill in skill.py** implementation
2. **Update skill.yaml** fields (connector, rules, trigger)
3. **Add test cases** for error paths
4. **Run tests** with `/test`
5. **Verify** Skill loads correctly with SkillLoader
