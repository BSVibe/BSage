# Ingest Compiler E2E Checklist

## Core Functionality
- [x] IngestCompiler.compile() returns CompileResult dataclass
- [x] Searches vault for related existing notes via retriever
- [x] Asks LLM to plan create/update/append actions
- [x] Creates new garden notes when LLM plans "create"
- [x] Updates existing notes when LLM plans "update"
- [x] Appends to existing notes when LLM plans "append"
- [x] Cross-references (related links) added to created notes

## Safety & Limits
- [x] Respects max_updates cap (truncates plan)
- [x] Skips actions with missing required fields
- [x] Skips update/append on nonexistent files (FileNotFoundError)
- [x] Handles malformed LLM JSON response without crashing
- [x] Handles empty LLM plan (returns zero counts)

## Integration
- [x] EventType.INGEST_COMPILE_START and INGEST_COMPILE_COMPLETE added
- [x] Emits events via EventBus during compile
- [x] Config settings: ingest_compile_enabled, ingest_compile_max_updates
- [x] Wired into AgentLoop.on_input() after seed writing
- [x] Wired into AppState.initialize() with DI
- [x] Optional (None) — existing behavior unchanged when disabled

## Code Quality
- [x] ruff check passes (no lint errors)
- [x] ruff format passes
- [x] 27 new unit tests across 4 modules
- [x] 1265 total tests passing (no regressions)
- [x] Coverage 90.67% (>80% threshold)
