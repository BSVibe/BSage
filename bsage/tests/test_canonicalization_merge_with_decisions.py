"""Tests for MergeConcepts cannot-link Hard Block (Handoff §7.2 + §8.5).

When a cannot-link decision between the canonical and any merge target
reaches the policy ``hard_blocks.cannot_link_threshold``, MergeConcepts
MUST block before any mutation.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from bsage.garden.canonicalization import models
from bsage.garden.canonicalization.decisions import DecisionMemory
from bsage.garden.canonicalization.index import InMemoryCanonicalizationIndex
from bsage.garden.canonicalization.lock import AsyncIOMutationLock
from bsage.garden.canonicalization.policies import PolicyResolver
from bsage.garden.canonicalization.resolver import TagResolver
from bsage.garden.canonicalization.service import CanonicalizationService
from bsage.garden.canonicalization.store import NoteStore
from bsage.garden.markdown_utils import extract_frontmatter
from bsage.garden.storage import FileSystemStorage


@pytest.fixture
def storage(tmp_path: Path) -> FileSystemStorage:
    return FileSystemStorage(tmp_path)


@pytest.fixture
async def service(storage: FileSystemStorage) -> CanonicalizationService:
    fixed_now = datetime(2026, 5, 7, 14, 0, 0)
    index = InMemoryCanonicalizationIndex()
    await index.initialize(storage)
    store = NoteStore(storage)
    decisions = DecisionMemory(index=index, store=store)
    policy_resolver = PolicyResolver(index=index, store=store, clock=lambda: fixed_now)
    svc = CanonicalizationService(
        store=store,
        lock=AsyncIOMutationLock(),
        index=index,
        resolver=TagResolver(index=index),
        decisions=decisions,
        policies=policy_resolver,
        clock=lambda: fixed_now,
    )
    # Bootstrap default policies so the cannot_link_threshold is in effect
    await policy_resolver.bootstrap_defaults()
    return svc


async def _seed_active(service: CanonicalizationService, concept_id: str) -> None:
    path = await service.create_action_draft(
        kind="create-concept",
        params={"concept": concept_id, "title": concept_id, "aliases": []},
    )
    await service.apply_action(path, actor="test")


async def _seed_cannot_link(
    service: CanonicalizationService,
    a: str,
    b: str,
    *,
    base_confidence: float,
    decay_profile: str = "definitional",
) -> str:
    decision_path = f"decisions/cannot-link/20260507-140000-{a}-{b}.md"
    await service._store.write_decision(
        models.DecisionEntry(
            path=decision_path,
            kind="cannot-link",
            status="active",
            maturity="seedling",
            decision_schema_version="cannot-link-v1",
            subjects=(a, b),
            base_confidence=base_confidence,
            last_confirmed_at=datetime(2026, 5, 7),
            decay_profile=decay_profile,
            decay_halflife_days=None,
            valid_from=datetime(2026, 5, 7),
            created_at=datetime(2026, 5, 7),
            updated_at=datetime(2026, 5, 7),
        )
    )
    await service._index.invalidate(decision_path)
    return decision_path


class TestCannotLinkHardBlock:
    @pytest.mark.asyncio
    async def test_strong_cannot_link_blocks_merge(
        self, service: CanonicalizationService, storage: FileSystemStorage
    ) -> None:
        await _seed_active(service, "ci")
        await _seed_active(service, "cd")
        await _seed_cannot_link(service, "ci", "cd", base_confidence=0.95)

        path = await service.create_action_draft(
            kind="merge-concepts",
            params={"canonical": "ci", "merge": ["cd"]},
        )
        result = await service.apply_action(path, actor="test")
        assert result.final_status == "blocked"

        # Verify Hard Block evidence references the decision
        action_fm = extract_frontmatter(await storage.read(path))
        hard_blocks = action_fm["validation"]["hard_blocks"]
        assert any("cannot_link" in (b.get("payload", {}).get("reason") or "") for b in hard_blocks)
        # Old active concept untouched
        assert await storage.exists("concepts/active/cd.md")
        assert not await storage.exists("concepts/merged/cd.md")

    @pytest.mark.asyncio
    async def test_weak_cannot_link_does_not_block(
        self, service: CanonicalizationService, storage: FileSystemStorage
    ) -> None:
        await _seed_active(service, "ci")
        await _seed_active(service, "cd")
        # 0.50 is below default 0.85 threshold
        await _seed_cannot_link(service, "ci", "cd", base_confidence=0.50)

        path = await service.create_action_draft(
            kind="merge-concepts",
            params={"canonical": "ci", "merge": ["cd"]},
        )
        result = await service.apply_action(path, actor="test")
        assert result.final_status == "applied"

    @pytest.mark.asyncio
    async def test_cannot_link_subject_order_independent(
        self, service: CanonicalizationService
    ) -> None:
        await _seed_active(service, "ci")
        await _seed_active(service, "cd")
        # Decision recorded as (cd, ci) — should still block (cd → ci) merge
        await _seed_cannot_link(service, "cd", "ci", base_confidence=0.95)

        path = await service.create_action_draft(
            kind="merge-concepts",
            params={"canonical": "ci", "merge": ["cd"]},
        )
        result = await service.apply_action(path, actor="test")
        assert result.final_status == "blocked"

    @pytest.mark.asyncio
    async def test_cannot_link_only_blocks_relevant_pair(
        self, service: CanonicalizationService
    ) -> None:
        # cannot-link between ci/cd, but merge a/b which is unrelated
        for c in ("ci", "cd", "a", "b"):
            await _seed_active(service, c)
        await _seed_cannot_link(service, "ci", "cd", base_confidence=0.95)

        path = await service.create_action_draft(
            kind="merge-concepts",
            params={"canonical": "a", "merge": ["b"]},
        )
        result = await service.apply_action(path, actor="test")
        assert result.final_status == "applied"

    @pytest.mark.asyncio
    async def test_superseded_cannot_link_does_not_block(
        self, service: CanonicalizationService
    ) -> None:
        await _seed_active(service, "ci")
        await _seed_active(service, "cd")

        # Old strong cannot-link, then superseded
        old_path = await _seed_cannot_link(service, "ci", "cd", base_confidence=0.95)
        old = await service._store.read_decision(old_path)
        assert old is not None
        old.status = "superseded"
        await service._store.write_decision(old)
        await service._index.invalidate(old_path)

        path = await service.create_action_draft(
            kind="merge-concepts",
            params={"canonical": "ci", "merge": ["cd"]},
        )
        result = await service.apply_action(path, actor="test")
        assert result.final_status == "applied"
