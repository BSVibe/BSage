# Skill System Rules

## CRITICAL: Skill 설계 및 구현 규칙

### 1. Skill 포맷

**모든 Skill은 `skills/` 디렉토리에 독립 폴더로 존재한다.**

```
skills/
├── garden-writer/
│   ├── skill.yaml      # 필수 — 메타데이터
│   └── skill.py        # 선택 — 코드 실행 필요 시
├── calendar-input/
│   ├── skill.yaml
│   └── skill.py
└── weekly-digest/
    └── skill.yaml      # yaml only — LLM 지시만으로 처리
```

### 2. skill.yaml 필수 필드

```yaml
name: garden-writer
version: 1.0.0
author: bslab
category: process              # input / process / output / meta
is_dangerous: false            # true면 SafeModeGuard 승인 필수
requires_connector: null       # Connector 이름 또는 null
description: 수집 데이터를 Obsidian 마크다운으로 정리

# InputSkill 전용
trigger:                       # category: input일 때만
  type: cron                   # cron / webhook / event
  schedule: "*/15 * * * *"

# ProcessSkill 체인
rules:                         # 이 Skill 실행 후 자동으로 이어질 Skill
  - insight-linker

# 코드 실행 시
entrypoint: skill.py::execute  # py 필요 시에만 명시
```

**NEVER 누락해서는 안 되는 필드:**
- `name`, `version`, `category`, `is_dangerous`, `description`

### 3. skill.py 규칙

**순수 Python. `bsage` 패키지 import 금지.**

```python
# Correct
async def execute(context):
    events = await context.connector("google-calendar").fetch_events()
    await context.garden.write_seed("calendar", events)
    return {"collected": len(events)}

# Wrong — bsage import 사용
from bsage.core.config import settings  # NO!
```

**규칙:**
- 진입점: `execute(context)` 함수 고정 (async)
- `context` 객체를 통해서만 외부 접근
- 표준 라이브러리 + PyPI 패키지만 사용
- `bsage` 내부 모듈 직접 import 금지

### 4. SkillContext 인터페이스

Skill은 `context` 객체를 통해서만 Core Engine과 소통한다.

```python
# context가 제공하는 인터페이스
context.connector(name: str)       # Connector 접근
context.garden.write_seed(...)     # seeds/ 쓰기
context.garden.write_garden(...)   # garden/ 쓰기
context.garden.write_action(...)   # actions/ 로그
context.garden.read_notes(...)     # 기존 노트 읽기
context.llm.chat(...)              # LLM API 호출
context.config                     # Skill 설정값 접근
context.logger                     # structlog 로거
```

### 5. is_dangerous 규칙

**외부 세계에 부작용을 발생시키는 Skill은 반드시 `is_dangerous: true`.**

```yaml
# Dangerous — 외부에 영향
calendar-writer:    is_dangerous: true   # 캘린더 일정 등록
email-sender:       is_dangerous: true   # 이메일 발송
telegram-sender:    is_dangerous: true   # 메시지 발송

# Safe — Vault 내부 작업만
garden-writer:      is_dangerous: false  # 마크다운 정리
insight-linker:     is_dangerous: false  # 노트 연결 발견
weekly-digest:      is_dangerous: false  # 리포트 생성
```

**SafeModeGuard가 `is_dangerous: true` Skill 실행 전 반드시 사용자 승인을 요청한다.**

### 6. Connector 접근 규칙

**Skill은 Connector에 직접 접근하지 않는다. 반드시 `context.connector()` 경유.**

```python
# Correct
async def execute(context):
    cal = context.connector("google-calendar")
    events = await cal.fetch_events()

# Wrong — 직접 API 호출
import googleapiclient  # NO! Connector를 통해서만
```

**`requires_connector` 필드에 명시된 Connector가 미연결 상태면 Skill 실행 자체가 차단된다.**

### 7. ProcessSkill 체인 결정

```
InputSkill 결과 도착
        ↓
1. yaml rules 확인 → 있으면 즉시 실행 (LLM 비용 없음)
2. rules 없거나 복잡한 판단 필요 → LLM 판단
3. LLM 판단 결과는 향후 rule로 추가 가능
```

**규칙 기반 실행이 우선. LLM 판단은 fallback.**

### 8. GardenWriter 쓰기 규칙

| 디렉토리 | 누가 쓰는가 | 내용 |
|---|---|---|
| `seeds/` | InputSkill 실행 후 | 원시 수집 데이터 |
| `garden/` | ProcessSkill 실행 후 | 정리된 지식 노트 |
| `actions/` | 모든 Skill 실행 후 | 에이전트 행동 로그 |

**ALWAYS use frontmatter:**
```markdown
---
type: idea
status: growing
source: calendar-input
captured_at: 2026-02-22
related: [[BSage]]
---
```

## Verification Checklist

Skill 구현 전:
- [ ] skill.yaml에 필수 필드 모두 존재
- [ ] is_dangerous 적절히 설정
- [ ] skill.py에서 bsage import 없음
- [ ] execute(context) 진입점 사용
- [ ] Connector 접근은 context.connector() 경유
- [ ] GardenWriter로 적절한 디렉토리에 쓰기
- [ ] 테스트에서 context mock 사용
