"""Tests for IngestCompiler ↔ CanonicalizationService integration (Handoff §11).

Slice 2: LLM-emitted raw tags MUST be canonicalized before landing in
garden note frontmatter. ``_clean_tags`` filters shape; the canon hook
filters meaning.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from bsage.garden.canonicalization.index import InMemoryCanonicalizationIndex
from bsage.garden.canonicalization.lock import AsyncIOMutationLock
from bsage.garden.canonicalization.resolver import TagResolver
from bsage.garden.canonicalization.service import CanonicalizationService
from bsage.garden.canonicalization.store import NoteStore
from bsage.garden.ingest_compiler import BatchItem, IngestCompiler
from bsage.garden.markdown_utils import extract_frontmatter
from bsage.garden.storage import FileSystemStorage
from bsage.garden.vault import Vault
from bsage.garden.writer import GardenWriter


@pytest.fixture
def vault_obj(tmp_path: Path) -> Vault:
    vault = Vault(tmp_path)
    vault.ensure_dirs()
    return vault


@pytest.fixture
def vault_dir(vault_obj: Vault) -> Path:
    return vault_obj.root


@pytest.fixture
def writer(vault_obj: Vault) -> GardenWriter:
    return GardenWriter(vault=vault_obj, default_tenant_id="tenant-default")


@pytest.fixture
def storage(vault_dir: Path) -> FileSystemStorage:
    return FileSystemStorage(vault_dir)


@pytest.fixture
async def canon_service(storage: FileSystemStorage) -> CanonicalizationService:
    fixed_now = datetime(2026, 5, 6, 14, 30, 12)
    index = InMemoryCanonicalizationIndex()
    await index.initialize(storage)
    return CanonicalizationService(
        store=NoteStore(storage),
        lock=AsyncIOMutationLock(),
        index=index,
        resolver=TagResolver(index=index),
        clock=lambda: fixed_now,
    )


def _llm(plan: list[dict]) -> AsyncMock:
    mock = AsyncMock()
    mock.chat = AsyncMock(return_value=json.dumps(plan))
    return mock


@pytest.fixture
def retriever() -> AsyncMock:
    r = AsyncMock()
    r.search = AsyncMock(return_value=[])
    return r


class TestIngestResolvesExistingConcept:
    @pytest.mark.asyncio
    async def test_alias_resolves_to_canonical(
        self,
        writer: GardenWriter,
        retriever: AsyncMock,
        canon_service: CanonicalizationService,
        vault_dir: Path,
    ) -> None:
        # Set up an active concept with an alias
        path = await canon_service.create_action_draft(
            kind="create-concept",
            params={
                "concept": "machine-learning",
                "title": "Machine Learning",
                "aliases": ["ml"],
            },
        )
        await canon_service.apply_action(path, actor="test")

        # LLM emits raw alias 'ml' as a tag
        plan = [
            {
                "action": "create",
                "title": "ML Note",
                "content": "Some content.",
                "tags": ["ml"],
                "reason": "Test ingest",
            }
        ]
        compiler = IngestCompiler(
            garden_writer=writer,
            llm_client=_llm(plan),
            retriever=retriever,
            canonicalization_service=canon_service,
        )
        result = await compiler.compile_batch(
            [BatchItem(label="seed", content="content")], "test-source"
        )
        assert result.notes_created == 1

        # Garden note should have canonical tag, not raw alias
        garden = list((vault_dir / "garden" / "seedling").glob("*.md"))
        assert len(garden) == 1
        fm = extract_frontmatter(garden[0].read_text())
        assert fm["tags"] == ["machine-learning"]


class TestIngestCreatesNewConceptDraft:
    @pytest.mark.asyncio
    async def test_unknown_tag_auto_creates_concept(
        self,
        writer: GardenWriter,
        retriever: AsyncMock,
        canon_service: CanonicalizationService,
        vault_dir: Path,
    ) -> None:
        plan = [
            {
                "action": "create",
                "title": "Self-host Note",
                "content": "Some content.",
                "tags": ["self-hosting"],
                "reason": "Test ingest",
            }
        ]
        compiler = IngestCompiler(
            garden_writer=writer,
            llm_client=_llm(plan),
            retriever=retriever,
            canonicalization_service=canon_service,
        )
        await compiler.compile_batch([BatchItem(label="seed", content="content")], "test-source")

        # New concept auto-applied
        assert (vault_dir / "concepts" / "active" / "self-hosting.md").exists()
        # Garden note has the new canonical id
        garden = list((vault_dir / "garden" / "seedling").glob("*.md"))
        fm = extract_frontmatter(garden[0].read_text())
        assert fm["tags"] == ["self-hosting"]


class TestIngestDropsAmbiguous:
    @pytest.mark.asyncio
    async def test_ambiguous_tag_dropped_from_garden(
        self,
        writer: GardenWriter,
        retriever: AsyncMock,
        canon_service: CanonicalizationService,
        vault_dir: Path,
    ) -> None:
        # Set up alias collision
        for cid in ("machine-learning", "meta-learning"):
            path = await canon_service.create_action_draft(
                kind="create-concept",
                params={"concept": cid, "title": cid, "aliases": ["ml-thing"]},
            )
            await canon_service.apply_action(path, actor="test")

        plan = [
            {
                "action": "create",
                "title": "Note",
                "content": "Content.",
                "tags": ["ml-thing", "machine-learning"],  # one ambiguous, one ok
                "reason": "test",
            }
        ]
        compiler = IngestCompiler(
            garden_writer=writer,
            llm_client=_llm(plan),
            retriever=retriever,
            canonicalization_service=canon_service,
        )
        await compiler.compile_batch([BatchItem(label="seed", content="content")], "test-source")

        garden = list((vault_dir / "garden" / "seedling").glob("*.md"))
        fm = extract_frontmatter(garden[0].read_text())
        # Ambiguous "ml-thing" dropped; "machine-learning" passes through
        assert fm["tags"] == ["machine-learning"]


class TestIngestWithoutCanonService:
    @pytest.mark.asyncio
    async def test_no_canon_service_keeps_raw_tags(
        self,
        writer: GardenWriter,
        retriever: AsyncMock,
        vault_dir: Path,
    ) -> None:
        # Backwards-compat: when canonicalization_service is not wired,
        # tags pass through _clean_tags only.
        plan = [
            {
                "action": "create",
                "title": "Note",
                "content": "Content.",
                "tags": ["self-hosting", "ml"],
                "reason": "test",
            }
        ]
        compiler = IngestCompiler(
            garden_writer=writer,
            llm_client=_llm(plan),
            retriever=retriever,
        )
        await compiler.compile_batch([BatchItem(label="seed", content="content")], "test-source")

        garden = list((vault_dir / "garden" / "seedling").glob("*.md"))
        fm = extract_frontmatter(garden[0].read_text())
        # Both raw tags survive — no canon hook applied
        assert set(fm["tags"]) == {"self-hosting", "ml"}


class TestIngestPendingCandidate:
    @pytest.mark.asyncio
    async def test_second_seed_appends_evidence_and_drops_tag(
        self,
        writer: GardenWriter,
        retriever: AsyncMock,
        storage: FileSystemStorage,
        vault_dir: Path,
    ) -> None:
        # Build a service with auto_apply OFF so first seed leaves a draft
        # rather than auto-creating an active concept.
        fixed_now = datetime(2026, 5, 6, 14, 30, 12)
        index = InMemoryCanonicalizationIndex()
        await index.initialize(storage)
        no_apply_service = _NoAutoApplyService(
            store=NoteStore(storage),
            lock=AsyncIOMutationLock(),
            index=index,
            resolver=TagResolver(index=index),
            clock=lambda: fixed_now,
        )

        # First seed: creates a draft, drops tag from garden
        plan = [
            {
                "action": "create",
                "title": "First",
                "content": "First content.",
                "tags": ["self-hosting"],
                "reason": "test",
            }
        ]
        compiler = IngestCompiler(
            garden_writer=writer,
            llm_client=_llm(plan),
            retriever=retriever,
            canonicalization_service=no_apply_service,
        )
        await compiler.compile_batch([BatchItem(label="seed1", content="first")], "test-source")

        action_files = await storage.list_files("actions/create-concept")
        assert len(action_files) == 1
        existing_draft = action_files[0]

        # Second seed: same tag, should NOT create another draft —
        # should append ingest_pending_candidate evidence.
        plan2 = [
            {
                "action": "create",
                "title": "Second",
                "content": "Second content.",
                "tags": ["self-hosting"],
                "reason": "test",
            }
        ]
        compiler2 = IngestCompiler(
            garden_writer=writer,
            llm_client=_llm(plan2),
            retriever=retriever,
            canonicalization_service=no_apply_service,
        )
        await compiler2.compile_batch([BatchItem(label="seed2", content="second")], "test-source")

        # Still only one draft
        action_files = await storage.list_files("actions/create-concept")
        assert action_files == [existing_draft]

        # Evidence was appended
        raw = await storage.read(existing_draft)
        fm = extract_frontmatter(raw)
        evidence = fm.get("evidence") or []
        assert len(evidence) == 1
        assert evidence[0]["kind"] == "ingest_pending_candidate"


class _NoAutoApplyService(CanonicalizationService):
    """Test helper — overrides resolve_and_canonicalize default to auto_apply=False."""

    async def resolve_and_canonicalize(  # type: ignore[override]
        self,
        raw_tag: str,
        *,
        raw_source: str | None = None,
        auto_apply: bool = False,
    ) -> str | None:
        return await super().resolve_and_canonicalize(
            raw_tag, raw_source=raw_source, auto_apply=auto_apply
        )
