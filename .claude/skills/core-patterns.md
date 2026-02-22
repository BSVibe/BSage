---
name: core-patterns
description: BSage Core Engine 구현 패턴 및 데이터 흐름
---

# Core Patterns Skill

## 실행 흐름

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

## SkillLoader 패턴

```python
from dataclasses import dataclass, field
from pathlib import Path

import structlog
import yaml

logger = structlog.get_logger(__name__)


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


class SkillLoader:
    def __init__(self, skills_dir: Path) -> None:
        self._skills_dir = skills_dir
        self._registry: dict[str, SkillMeta] = {}

    async def load_all(self) -> dict[str, SkillMeta]:
        """skills/ 디렉토리를 스캔하여 모든 Skill 메타데이터를 로드."""
        for skill_dir in self._skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            yaml_path = skill_dir / "skill.yaml"
            if not yaml_path.exists():
                logger.warning("skill_missing_yaml", path=str(skill_dir))
                continue
            meta = self._parse_yaml(yaml_path)
            self._registry[meta.name] = meta
            logger.info("skill_loaded", name=meta.name, category=meta.category)
        return self._registry

    def _parse_yaml(self, path: Path) -> SkillMeta:
        with open(path) as f:
            data = yaml.safe_load(f)
        return SkillMeta(**{k: v for k, v in data.items() if k in SkillMeta.__dataclass_fields__})
```

## SkillRunner 패턴

```python
import importlib.util
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class SkillRunner:
    async def run(self, skill_meta: SkillMeta, context: SkillContext) -> dict:
        """Skill을 실행하고 결과를 반환."""
        logger.info("skill_run_start", name=skill_meta.name, category=skill_meta.category)

        if skill_meta.entrypoint:
            # py 실행
            module_name, func_name = skill_meta.entrypoint.split("::")
            skill_dir = self._skills_dir / skill_meta.name
            result = await self._run_python(skill_dir / module_name, func_name, context)
        else:
            # yaml only — LLM 기반 처리
            result = await self._run_llm(skill_meta, context)

        logger.info("skill_run_complete", name=skill_meta.name)
        return result

    async def _run_python(self, module_path: Path, func_name: str, context: SkillContext) -> dict:
        spec = importlib.util.spec_from_file_location("skill_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        func = getattr(module, func_name)
        return await func(context)

    async def _run_llm(self, skill_meta: SkillMeta, context: SkillContext) -> dict:
        # LLM에게 skill.yaml의 description을 기반으로 처리 지시
        response = await context.llm.chat(
            system=f"You are executing the '{skill_meta.name}' skill: {skill_meta.description}",
            messages=[{"role": "user", "content": str(context.input_data)}],
        )
        return {"llm_response": response}
```

## AgentLoop 패턴

```python
class AgentLoop:
    async def on_input(self, skill_name: str, raw_data: dict) -> None:
        """InputSkill 결과 수신 → ProcessSkill 체인 결정 → 실행."""
        # 1. seeds에 원시 데이터 저장
        await self._garden_writer.write_seed(skill_name, raw_data)

        # 2. rules 확인 (yaml 기반 우선)
        input_meta = self._registry[skill_name]
        if input_meta.rules:
            process_skills = input_meta.rules
        else:
            # 3. LLM fallback
            process_skills = await self._decide_with_llm(skill_name, raw_data)

        # 4. ProcessSkill 체인 실행
        for ps_name in process_skills:
            ps_meta = self._registry[ps_name]

            # SafeModeGuard 체크
            if ps_meta.is_dangerous:
                approved = await self._safe_mode.request_approval(ps_meta)
                if not approved:
                    logger.warning("skill_rejected", name=ps_name)
                    continue

            await self._skill_runner.run(ps_meta, context)
```

## SafeModeGuard 패턴

```python
class SafeModeGuard:
    async def check(self, skill_meta: SkillMeta) -> bool:
        """is_dangerous=True Skill에 대해 사용자 승인을 요청."""
        if not skill_meta.is_dangerous:
            return True

        logger.info("safe_mode_approval_required",
                     skill=skill_meta.name,
                     description=skill_meta.description)

        # Interface 레이어로 승인 요청 위임
        return await self._interface.request_approval(
            skill_name=skill_meta.name,
            description=skill_meta.description,
            action_summary=f"[{skill_meta.category}] {skill_meta.description}",
        )
```

## GardenWriter 패턴

```python
from datetime import datetime
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


class GardenWriter:
    def __init__(self, vault_path: Path) -> None:
        self._vault = vault_path

    async def write_seed(self, source: str, data: dict) -> Path:
        """InputSkill 결과를 seeds/에 저장."""
        dest = self._vault / "seeds" / source
        dest.mkdir(parents=True, exist_ok=True)
        note_path = dest / f"{datetime.now():%Y-%m-%d_%H%M}.md"
        content = self._format_seed(source, data)
        note_path.write_text(content, encoding="utf-8")
        logger.info("seed_written", path=str(note_path))
        return note_path

    async def write_action(self, skill_name: str, summary: str) -> None:
        """에이전트 행동 로그를 actions/에 기록."""
        today = self._vault / "actions" / f"{datetime.now():%Y-%m-%d}.md"
        today.parent.mkdir(parents=True, exist_ok=True)
        entry = f"\n## {datetime.now():%H:%M} — {skill_name}\n{summary}\n"
        with open(today, "a", encoding="utf-8") as f:
            f.write(entry)

    def _format_seed(self, source: str, data: dict) -> str:
        return (
            f"---\ntype: seed\nsource: {source}\n"
            f"captured_at: {datetime.now():%Y-%m-%d}\n---\n\n"
            f"{data}\n"
        )
```

## CredentialStore 패턴

```python
class CredentialStore:
    """JSON 파일 기반 credential 저장/로드."""

    def __init__(self, credentials_dir: Path) -> None:
        self._dir = credentials_dir

    async def get(self, name: str) -> dict[str, Any]:
        """name.json에서 credential 로드. 없으면 CredentialNotFoundError."""

    async def store(self, name: str, data: dict[str, Any]) -> None:
        """name.json으로 credential 저장."""

    def list_services(self) -> list[str]:
        """저장된 credential 목록 반환."""
```

## Scheduler 패턴

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

class Scheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    async def register_triggers(self, registry: dict[str, SkillMeta]) -> None:
        """InputSkill의 trigger를 스케줄러에 등록."""
        for name, meta in registry.items():
            if meta.category != "input" or not meta.trigger:
                continue

            match meta.trigger["type"]:
                case "cron":
                    self._scheduler.add_job(
                        self._run_input_skill,
                        "cron",
                        args=[name],
                        **self._parse_cron(meta.trigger["schedule"]),
                    )
                case "webhook":
                    await self._register_webhook(name, meta.trigger)
                case "event":
                    await self._register_event(name, meta.trigger)

            logger.info("trigger_registered", skill=name, type=meta.trigger["type"])

    def start(self) -> None:
        self._scheduler.start()
```

## Critical Rules

1. **Skill은 Core 내부 구조를 몰라도 된다** — `context` 객체만 사용
2. **규칙 기반 실행이 LLM 판단보다 우선** — 예측 가능성 + 비용 절감
3. **is_dangerous 체크는 건너뛸 수 없다** — SafeModeGuard 우회 금지
4. **Vault 밖으로 데이터 유출 없음** — GardenWriter만 Vault에 쓰기
5. **외부 서비스 연결은 Skill이 자체 처리** — credential은 context.credentials로 로드
