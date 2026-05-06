"""CanonicalizationService — slice-1 minimal facade (Class_Diagram §5).

Slice 1 exposes only ``create_action_draft`` + ``apply_action`` for the two
in-scope action kinds (``create-concept``, ``retag-notes``). All other kinds
raise ``NotImplementedError``. Proposals, decisions, policies, scoring, Safe
Mode, REST, MCP, watcher, and cron come in slices 2-6.

Spec invariants honored from slice 1 (Handoff §0):
- §0.1 vault is SoT — only ``StorageBackend`` writes happen here
- §0.2 path/frontmatter different jobs — kind/role come from path
- §0.5 typed action mutation — every concept/garden mutation is a typed action
- §0.11 single-writer per action_path — apply pipeline holds the lock
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any

from bsage.garden.canonicalization import models, paths
from bsage.garden.canonicalization.index import CanonicalizationIndex
from bsage.garden.canonicalization.lock import AsyncIOMutationLock
from bsage.garden.canonicalization.resolver import TagResolver
from bsage.garden.canonicalization.store import NoteStore

_DEFAULT_EXPIRY = timedelta(days=1)
_SLICE_1_KINDS: frozenset[str] = frozenset({"create-concept", "retag-notes"})

_ACTION_SCHEMA_VERSIONS: dict[str, str] = {
    "create-concept": "create-concept-v1",
    "retag-notes": "retag-notes-v1",
}


def _title_from_raw(raw_tag: str) -> str:
    """Best-effort human title from a raw tag for auto-applied CreateConcept.

    Used only when ingest auto-creates a new concept. The vault user can
    rename the H1 later through normal markdown editing; the concept id
    (file stem) is the stable handle.
    """
    cleaned = raw_tag.strip()
    if not cleaned:
        return "Untitled Concept"
    return " ".join(part.capitalize() for part in cleaned.replace("_", " ").split())


def _evidence(reason: str, **payload: Any) -> dict[str, Any]:
    """Minimal Hard Block evidence envelope (Handoff §2 Evidence)."""
    return {
        "kind": "deterministic_check",
        "schema_version": "deterministic-check-v1",
        "source": "deterministic",
        "observed_at": datetime.now().isoformat(),
        "producer": "canonicalization.service-v1",
        "payload": {"reason": reason, **payload},
    }


class CanonicalizationService:
    """Slice 1+2 canonicalization facade.

    Slice 2 adds ``index`` + ``resolver`` for tag resolution and
    ``resolve_and_canonicalize`` for the IngestCompiler hook (Handoff §11).
    The index is kept fresh by invalidating affected paths after each
    successful apply.
    """

    def __init__(
        self,
        store: NoteStore,
        lock: AsyncIOMutationLock,
        *,
        index: CanonicalizationIndex | None = None,
        resolver: TagResolver | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = store
        self._lock = lock
        self._index = index
        self._resolver = resolver
        self._clock = clock or datetime.now

    # ---------------------------------------------------------------- drafts

    async def create_action_draft(
        self,
        kind: str,
        params: dict[str, Any],
        *,
        slug: str | None = None,
        source_proposal: str | None = None,
        expires_in: timedelta = _DEFAULT_EXPIRY,
    ) -> str:
        if kind not in _SLICE_1_KINDS:
            msg = f"action kind {kind!r} not in slice 1 (only {sorted(_SLICE_1_KINDS)})"
            raise NotImplementedError(msg)

        if slug is None:
            slug = self._derive_slug(kind, params)

        now = self._clock()
        candidate = paths.build_action_path(kind, now, slug)
        existing = await self._store.list_existing_action_paths(kind)
        action_path = paths.with_collision_suffix(candidate, existing)

        entry = models.ActionEntry(
            path=action_path,
            kind=kind,
            status="draft",
            action_schema_version=_ACTION_SCHEMA_VERSIONS[kind],
            params=dict(params),
            created_at=now,
            updated_at=now,
            expires_at=now + expires_in,
            source_proposal=source_proposal,
        )
        await self._store.write_action(entry)
        await self._invalidate_index([action_path])
        return action_path

    @staticmethod
    def _derive_slug(kind: str, params: dict[str, Any]) -> str:
        if kind == "create-concept":
            concept = params.get("concept", "")
            if not paths.is_valid_concept_id(concept):
                msg = f"create-concept needs valid 'concept' param: {concept!r}"
                raise ValueError(msg)
            return concept
        # retag-notes / other kinds: caller must supply slug
        msg = f"slug required for action kind {kind!r}"
        raise ValueError(msg)

    # ----------------------------------------------------------------- apply

    async def apply_action(self, action_path: str, *, actor: str) -> models.ApplyResult:
        async with self._lock.guard(action_path):
            return await self._apply_locked(action_path, actor=actor)

    async def _apply_locked(self, action_path: str, *, actor: str) -> models.ApplyResult:
        entry = await self._store.read_action(action_path)
        if entry is None:
            return models.ApplyResult(
                action_path=action_path,
                final_status="failed",
                affected_paths=[],
                error="action_note_not_found",
            )

        # Idempotency: applied actions are no-op (slice 1 simple semantic)
        if entry.status == "applied":
            return models.ApplyResult(
                action_path=action_path,
                final_status="applied",
                affected_paths=list(entry.affected_paths),
            )

        # Validate (deterministic Hard Blocks, Handoff §13)
        validation = await self._validate(entry)
        if validation.hard_blocks:
            return await self._persist_blocked(entry, validation)

        # Slice 1 has no scoring/Safe Mode/policy — go straight to effects
        try:
            affected = await self._persist_effects(entry)
        except Exception as exc:  # noqa: BLE001 — runtime failure logged into action
            entry.execution.status = "failed"
            entry.execution.error = repr(exc)
            entry.status = "failed"
            entry.updated_at = self._clock()
            await self._store.write_action(entry)
            return models.ApplyResult(
                action_path=action_path,
                final_status="failed",
                affected_paths=[],
                error=repr(exc),
            )

        now = self._clock()
        entry.validation = validation
        entry.execution.status = "ok"
        entry.execution.applied_at = now
        entry.execution.error = None
        entry.permission.safe_mode = False
        entry.permission.decision = "auto_apply"
        entry.permission.actor = actor
        entry.permission.decided_at = now
        entry.affected_paths = sorted({action_path, *affected})
        entry.status = "applied"
        entry.updated_at = now
        await self._store.write_action(entry)
        await self._invalidate_index(entry.affected_paths)

        return models.ApplyResult(
            action_path=action_path,
            final_status="applied",
            affected_paths=list(entry.affected_paths),
        )

    async def _invalidate_index(self, paths_: list[str]) -> None:
        if self._index is None:
            return
        for p in paths_:
            await self._index.invalidate(p)

    async def _persist_blocked(
        self,
        entry: models.ActionEntry,
        validation: models.ValidationResult,
    ) -> models.ApplyResult:
        now = self._clock()
        entry.validation = validation
        entry.status = "blocked"
        entry.updated_at = now
        await self._store.write_action(entry)
        await self._invalidate_index([entry.path])
        return models.ApplyResult(
            action_path=entry.path,
            final_status="blocked",
            affected_paths=[entry.path],
            error="hard_block",
        )

    # ---------------------------------------------------------------- resolve

    async def resolve_and_canonicalize(
        self,
        raw_tag: str,
        *,
        raw_source: str | None = None,
        auto_apply: bool = True,
    ) -> str | None:
        """Tag → canonical concept id (Handoff §11 ingest write policy).

        Returns the canonical id when the tag resolves (or auto-creates)
        cleanly. Returns None for ``ambiguous`` / ``blocked`` /
        ``pending_candidate``, and for ``new_candidate`` when ``auto_apply``
        is False — in those cases the caller MUST drop the raw tag from
        any final garden ``tags`` list (per spec).
        """
        if self._resolver is None:
            msg = "service has no resolver wired"
            raise RuntimeError(msg)

        result = await self._resolver.resolve(raw_tag)
        normalized = result.concept_id

        if result.status == "resolved":
            return result.concept_id

        if result.status == "pending_candidate":
            if normalized is not None and result.pending_draft is not None:
                await self._append_pending_evidence(
                    draft_path=result.pending_draft,
                    raw_tag=raw_tag,
                    normalized_tag=normalized,
                    raw_source=raw_source,
                )
            return None

        if result.status == "new_candidate" and normalized is not None:
            draft = await self.create_action_draft(
                kind="create-concept",
                params={"concept": normalized, "title": _title_from_raw(raw_tag)},
            )
            if not auto_apply:
                return None
            applied = await self.apply_action(draft, actor="ingest")
            if applied.final_status == "applied":
                return normalized
            return None

        # ambiguous / blocked
        return None

    async def _append_pending_evidence(
        self,
        *,
        draft_path: str,
        raw_tag: str,
        normalized_tag: str,
        raw_source: str | None,
    ) -> None:
        async with self._lock.guard(draft_path):
            entry = await self._store.read_action(draft_path)
            if entry is None or entry.status not in {"draft", "pending_approval"}:
                return
            evidence_item = {
                "kind": "ingest_pending_candidate",
                "schema_version": "ingest-pending-candidate-v1",
                "source": "system",
                "observed_at": self._clock().isoformat(),
                "producer": "canonicalization.ingest-v1",
                "payload": {
                    "raw_tag": raw_tag,
                    "normalized_tag": normalized_tag,
                    "raw_source": raw_source,
                },
            }
            entry.evidence = [*entry.evidence, evidence_item]
            entry.updated_at = self._clock()
            await self._store.write_action(entry)
            await self._invalidate_index([draft_path])

    # -------------------------------------------------------------- validate

    async def _validate(self, entry: models.ActionEntry) -> models.ValidationResult:
        result = models.ValidationResult(status="passed", hard_blocks=[])
        if entry.kind == "create-concept":
            await self._validate_create_concept(entry, result)
        elif entry.kind == "retag-notes":
            await self._validate_retag_notes(entry, result)
        else:  # pragma: no cover — guarded by create_action_draft
            result.hard_blocks.append(_evidence("unsupported_action_kind", kind=entry.kind))
        if result.hard_blocks:
            result.status = "failed"
        return result

    async def _validate_create_concept(
        self,
        entry: models.ActionEntry,
        result: models.ValidationResult,
    ) -> None:
        concept = entry.params.get("concept")
        title = entry.params.get("title")
        if not isinstance(concept, str) or not paths.is_valid_concept_id(concept):
            result.hard_blocks.append(_evidence("invalid_concept_id", concept=concept))
            return
        if not isinstance(title, str) or not title.strip():
            result.hard_blocks.append(_evidence("missing_title"))
            return
        if await self._store.concept_exists(concept):
            result.hard_blocks.append(_evidence("concept_already_exists", concept=concept))

    async def _validate_retag_notes(
        self,
        entry: models.ActionEntry,
        result: models.ValidationResult,
    ) -> None:
        changes = entry.params.get("changes")
        if not isinstance(changes, list) or not changes:
            result.hard_blocks.append(_evidence("missing_changes"))
            return
        for change in changes:
            if not isinstance(change, dict):
                result.hard_blocks.append(_evidence("malformed_change_entry"))
                continue
            path = change.get("path")
            if not isinstance(path, str) or not path.startswith("garden/"):
                result.hard_blocks.append(_evidence("retag_outside_garden", path=path))
                continue
            for tag in change.get("add_tags", []) or []:
                if not isinstance(tag, str) or not paths.is_valid_concept_id(tag):
                    result.hard_blocks.append(_evidence("invalid_tag_id", tag=tag))
                    continue
                if not await self._store.concept_exists(tag):
                    result.hard_blocks.append(_evidence("tag_not_active_concept", tag=tag))

    # -------------------------------------------------------------- effects

    async def _persist_effects(self, entry: models.ActionEntry) -> list[str]:
        if entry.kind == "create-concept":
            return await self._effect_create_concept(entry)
        if entry.kind == "retag-notes":
            return await self._effect_retag_notes(entry)
        msg = f"unsupported kind: {entry.kind!r}"  # pragma: no cover
        raise NotImplementedError(msg)

    async def _effect_create_concept(self, entry: models.ActionEntry) -> list[str]:
        concept = entry.params["concept"]
        title = entry.params["title"]
        aliases = list(entry.params.get("aliases") or [])
        initial_body = entry.params.get("initial_body")

        now = self._clock()
        path = paths.active_concept_path(concept)
        await self._store.write_concept(
            models.ConceptEntry(
                concept_id=concept,
                path=path,
                display=title,
                aliases=aliases,
                created_at=now,
                updated_at=now,
                source_action=entry.path,
            ),
            initial_body=initial_body,
        )
        return [path]

    async def _effect_retag_notes(self, entry: models.ActionEntry) -> list[str]:
        affected: list[str] = []
        for change in entry.params["changes"]:
            path = change["path"]
            current = await self._store.read_garden_tags(path)
            remove = set(change.get("remove_tags") or [])
            add = list(change.get("add_tags") or [])
            kept = [t for t in current if t not in remove]
            merged: list[str] = []
            seen: set[str] = set()
            for tag in [*kept, *add]:
                if tag not in seen:
                    seen.add(tag)
                    merged.append(tag)
            merged.sort()
            await self._store.set_garden_tags(path, merged)
            affected.append(path)
        return affected
