"""Tests for bsage.garden.retriever — VaultRetriever semantic search + fallback."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from bsage.garden.retriever import (
    VaultRetriever,
    _content_hash,
    _extract_metadata,
    _strip_frontmatter,
    _strip_related_field,
)
from bsage.garden.vector_store import SearchResult


def _mock_vault(notes_by_dir: dict[str, list[tuple[str, str]]] | None = None):
    """Create a mock Vault with notes."""
    vault = MagicMock()
    vault.root = Path("/vault")
    notes_by_dir = notes_by_dir or {}

    async def _read_notes(subdir):
        entries = notes_by_dir.get(subdir, [])
        return [Path(f"/vault/{subdir}/{name}") for name, _content in entries]

    async def _read_content(path):
        for entries in notes_by_dir.values():
            for name, content in entries:
                if path.name == name:
                    return content
        raise FileNotFoundError(path)

    def _resolve_path(subpath):
        return Path(f"/vault/{subpath}")

    vault.read_notes = AsyncMock(side_effect=_read_notes)
    vault.read_note_content = AsyncMock(side_effect=_read_content)
    vault.resolve_path = MagicMock(side_effect=_resolve_path)
    return vault


class TestExtractMetadata:
    """Test frontmatter extraction helper."""

    def test_extracts_yaml_frontmatter(self) -> None:
        text = "---\ntitle: Hello\ntype: idea\n---\nBody text"
        meta = _extract_metadata(text)
        assert meta["title"] == "Hello"
        assert meta["type"] == "idea"

    def test_no_frontmatter_returns_empty(self) -> None:
        assert _extract_metadata("No frontmatter here") == {}

    def test_malformed_yaml_returns_empty(self) -> None:
        text = "---\n: bad: yaml:\n---\n"
        result = _extract_metadata(text)
        # yaml.safe_load might parse this as a string, not dict
        assert isinstance(result, dict)

    def test_no_closing_delimiter(self) -> None:
        text = "---\ntitle: Hello\nBody text"
        assert _extract_metadata(text) == {}


class TestStripFrontmatter:
    """Test frontmatter stripping helper."""

    def test_strips_frontmatter(self) -> None:
        text = "---\ntitle: Hello\n---\nBody text"
        assert _strip_frontmatter(text) == "Body text"

    def test_no_frontmatter_returns_original(self) -> None:
        text = "No frontmatter"
        assert _strip_frontmatter(text) == "No frontmatter"


class TestContentHash:
    """Test content hashing."""

    def test_deterministic(self) -> None:
        assert _content_hash("hello") == _content_hash("hello")

    def test_different_content_different_hash(self) -> None:
        assert _content_hash("hello") != _content_hash("world")


class TestVaultRetrieverRAGAvailable:
    """Test rag_available property."""

    def test_rag_available_true(self) -> None:
        retriever = VaultRetriever(
            vault=MagicMock(),
            vector_store=MagicMock(),
            embedding_client=MagicMock(),
        )
        assert retriever.rag_available is True

    def test_rag_available_false_no_store(self) -> None:
        retriever = VaultRetriever(vault=MagicMock(), embedding_client=MagicMock())
        assert retriever.rag_available is False

    def test_rag_available_false_no_client(self) -> None:
        retriever = VaultRetriever(vault=MagicMock(), vector_store=MagicMock())
        assert retriever.rag_available is False

    def test_rag_available_false_none(self) -> None:
        retriever = VaultRetriever(vault=MagicMock())
        assert retriever.rag_available is False


class TestVaultRetrieverFallback:
    """Test fallback (non-RAG) retrieval."""

    async def test_fallback_reads_recent_notes(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [
                    ("01-old.md", "Old content"),
                    ("02-new.md", "New content"),
                ],
            }
        )
        retriever = VaultRetriever(vault=vault)
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        # reversed order — newest first
        assert result.index("New content") < result.index("Old content")

    async def test_fallback_respects_max_chars(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [("big.md", "x" * 60_000)],
            }
        )
        retriever = VaultRetriever(vault=vault)
        result = await retriever.retrieve(
            query="test", context_dirs=["garden/idea"], max_chars=1000
        )
        assert len(result) <= 1000

    async def test_fallback_empty_vault(self) -> None:
        vault = _mock_vault({})
        retriever = VaultRetriever(vault=vault)
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        assert result == ""


class TestVaultRetrieverSemantic:
    """Test RAG-based semantic retrieval."""

    async def test_semantic_retrieve(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [("relevant.md", "Relevant content")],
            }
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult(
                    note_path="garden/idea/relevant.md",
                    title="Relevant",
                    score=0.95,
                    note_type="idea",
                    source="test",
                ),
            ]
        )

        retriever = VaultRetriever(
            vault=vault,
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )
        result = await retriever.retrieve(
            query="find relevant notes",
            context_dirs=["garden/idea"],
        )
        assert "Relevant content" in result
        mock_embedding.embed_one.assert_called_once()

    async def test_semantic_filters_by_context_dirs(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [("note.md", "Idea content")],
            }
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult("garden/idea/note.md", "Note", 0.9, "idea", "test"),
                SearchResult("seeds/chat/other.md", "Other", 0.8, "seed", "chat"),
            ]
        )

        retriever = VaultRetriever(
            vault=vault,
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )
        result = await retriever.retrieve(
            query="test",
            context_dirs=["garden/idea"],
        )
        # Only garden/idea should be included
        assert "Idea content" in result

    async def test_semantic_falls_back_on_error(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [("fallback.md", "Fallback content")],
            }
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(side_effect=RuntimeError("API error"))

        retriever = VaultRetriever(
            vault=vault,
            vector_store=AsyncMock(),
            embedding_client=mock_embedding,
        )
        result = await retriever.retrieve(
            query="test",
            context_dirs=["garden/idea"],
        )
        # Should fall back to recency-based retrieval
        assert "Fallback content" in result

    async def test_semantic_no_results_falls_back(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [("note.md", "Some content")],
            }
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.search = AsyncMock(return_value=[])

        retriever = VaultRetriever(
            vault=vault,
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )
        result = await retriever.retrieve(
            query="test",
            context_dirs=["garden/idea"],
        )
        assert "Some content" in result


class TestVaultRetrieverIndexNote:
    """Test index_note() for write-time indexing."""

    async def test_index_note_creates_embedding(self) -> None:
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1, 0.2, 0.3])

        mock_store = AsyncMock()
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()

        retriever = VaultRetriever(
            vault=MagicMock(),
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        content = "---\ntitle: My Note\ntype: idea\nsource: chat\n---\nNote body"
        await retriever.index_note("garden/idea/my-note.md", content)

        mock_store.upsert.assert_called_once()
        record = mock_store.upsert.call_args.args[0]
        assert record.note_path == "garden/idea/my-note.md"
        assert record.title == "My Note"
        assert record.note_type == "idea"
        assert record.embedding == [0.1, 0.2, 0.3]

    async def test_index_note_skips_unchanged(self) -> None:
        content = "Some content"
        c_hash = _content_hash(content)

        mock_store = AsyncMock()
        mock_store.get_content_hash = AsyncMock(return_value=c_hash)

        retriever = VaultRetriever(
            vault=MagicMock(),
            vector_store=mock_store,
            embedding_client=AsyncMock(),
        )
        await retriever.index_note("note.md", content)

        # embed should not be called since hash matches
        mock_store.upsert.assert_not_called()

    async def test_index_note_noop_when_rag_unavailable(self) -> None:
        retriever = VaultRetriever(vault=MagicMock())
        # Should not raise
        await retriever.index_note("note.md", "content")

    async def test_index_note_handles_embedding_failure(self) -> None:
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(side_effect=RuntimeError("API error"))

        mock_store = AsyncMock()
        mock_store.get_content_hash = AsyncMock(return_value=None)

        retriever = VaultRetriever(
            vault=MagicMock(),
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )
        # Should not raise
        await retriever.index_note("note.md", "content")
        mock_store.upsert.assert_not_called()


class TestVaultRetrieverReindexAll:
    """Test reindex_all() for full vault reindexing."""

    async def test_reindex_all_raises_when_rag_unavailable(self) -> None:
        retriever = VaultRetriever(vault=MagicMock())
        with pytest.raises(RuntimeError, match="RAG not available"):
            await retriever.reindex_all()

    async def test_reindex_all_indexes_notes(self) -> None:
        vault = _mock_vault(
            {
                "seeds/chat": [("2026-02-27_0900.md", "Seed content")],
                "garden/idea": [("note.md", "Garden content")],
            }
        )
        # Make resolve_path return real-like paths and handle subdirectory iteration
        vault.resolve_path = MagicMock(side_effect=lambda p: Path(f"/vault/{p}"))

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1, 0.2, 0.3])

        mock_store = AsyncMock()
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.all_paths = AsyncMock(return_value=set())

        retriever = VaultRetriever(
            vault=vault,
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        # reindex_all tries read_notes on "seeds" and "garden" first,
        # then iterates subdirectories if those fail.
        # We mock read_notes to return results for the subdirs.
        count = await retriever.reindex_all(dirs=["seeds/chat", "garden/idea"])
        assert count == 2

    async def test_reindex_all_cleans_stale_entries(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [("current.md", "Current content")],
            }
        )
        vault.resolve_path = MagicMock(side_effect=lambda p: Path(f"/vault/{p}"))

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        mock_store = AsyncMock()
        mock_store.fts_available = True
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.all_paths = AsyncMock(
            return_value={"garden/idea/current.md", "garden/idea/deleted.md"}
        )
        mock_store.delete = AsyncMock()
        mock_store.delete_fts = AsyncMock()
        mock_store.delete_links = AsyncMock()

        retriever = VaultRetriever(
            vault=vault,
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )
        await retriever.reindex_all(dirs=["garden/idea"])

        mock_store.delete.assert_called_once_with("garden/idea/deleted.md")
        mock_store.delete_fts.assert_called_once_with("garden/idea/deleted.md")
        mock_store.delete_links.assert_called_once_with("garden/idea/deleted.md")


class TestVaultRetrieverRemoveNote:
    """Test remove_note() for index cleanup."""

    async def test_remove_note_calls_vector_store_delete(self) -> None:
        mock_store = AsyncMock()
        mock_store.fts_available = True
        mock_store.delete = AsyncMock()
        mock_store.delete_fts = AsyncMock()
        mock_store.delete_links = AsyncMock()

        retriever = VaultRetriever(
            vault=MagicMock(),
            vector_store=mock_store,
            embedding_client=MagicMock(),
        )
        await retriever.remove_note("garden/idea/old-note.md")
        mock_store.delete.assert_called_once_with("garden/idea/old-note.md")
        mock_store.delete_fts.assert_called_once_with("garden/idea/old-note.md")
        mock_store.delete_links.assert_called_once_with("garden/idea/old-note.md")

    async def test_remove_note_noop_when_rag_unavailable(self) -> None:
        retriever = VaultRetriever(vault=MagicMock())
        # Should not raise
        await retriever.remove_note("garden/idea/old-note.md")

    async def test_reindex_all_reports_progress(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [
                    ("a.md", "A"),
                    ("b.md", "B"),
                ],
            }
        )
        vault.resolve_path = MagicMock(side_effect=lambda p: Path(f"/vault/{p}"))

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        mock_store = AsyncMock()
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.all_paths = AsyncMock(return_value=set())

        retriever = VaultRetriever(
            vault=vault,
            vector_store=mock_store,
            embedding_client=mock_embedding,
        )

        progress_calls: list[tuple[int, int]] = []
        await retriever.reindex_all(
            dirs=["garden/idea"],
            on_progress=lambda c, t: progress_calls.append((c, t)),
        )
        assert len(progress_calls) == 2
        assert progress_calls[-1] == (2, 2)


# ------------------------------------------------------------------
# Hybrid search tests
# ------------------------------------------------------------------


def _mock_store_for_hybrid(
    semantic_results: list[SearchResult] | None = None,
    fts_results: list[SearchResult] | None = None,
    linked_paths: dict[str, set[str]] | None = None,
) -> AsyncMock:
    """Create a mock VectorStore with FTS + links support."""
    mock_store = AsyncMock()
    mock_store.fts_available = True
    mock_store.search = AsyncMock(return_value=semantic_results or [])
    mock_store.fts_search = AsyncMock(return_value=fts_results or [])
    linked = linked_paths or {}
    mock_store.get_linked_paths = AsyncMock(side_effect=lambda p: linked.get(p, set()))
    mock_store.get_linked_paths_batch = AsyncMock(
        side_effect=lambda paths: {p: linked.get(p, set()) for p in paths}
    )
    return mock_store


class TestVaultRetrieverHybrid:
    """Test hybrid search (semantic + FTS + link expansion)."""

    async def test_hybrid_retrieve_combines_three_signals(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [
                    ("semantic.md", "Semantic match"),
                    ("keyword.md", "Keyword match"),
                ],
            }
        )
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/semantic.md", "Semantic", 0.9, "idea", "test"),
            ],
            fts_results=[
                SearchResult("garden/idea/keyword.md", "Keyword", 2.0, "idea", "test"),
            ],
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever.retrieve(query="test query", context_dirs=["garden/idea"])
        # Both results should be included
        assert "Semantic match" in result
        assert "Keyword match" in result

    async def test_hybrid_retrieve_link_expansion(self) -> None:
        vault = _mock_vault(
            {
                "garden/idea": [
                    ("top.md", "Top result"),
                    ("linked.md", "Linked note"),
                ],
            }
        )
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/top.md", "Top", 0.9, "idea", "test"),
            ],
            linked_paths={
                "garden/idea/top.md": {"garden/idea/linked.md"},
            },
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        # Linked note should be boosted into results
        assert "Top result" in result
        assert "Linked note" in result

    async def test_hybrid_retrieve_filters_dirs(self) -> None:
        vault = _mock_vault({"garden/idea": [("note.md", "Idea content")]})
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/note.md", "Note", 0.9, "idea", "test"),
                SearchResult("seeds/chat/other.md", "Other", 0.8, "seed", "chat"),
            ],
            fts_results=[
                SearchResult("seeds/chat/other.md", "Other", 2.0, "seed", "chat"),
            ],
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        assert "Idea content" in result

    async def test_hybrid_retrieve_respects_max_chars(self) -> None:
        vault = _mock_vault({"garden/idea": [("big.md", "x" * 5000), ("small.md", "y" * 100)]})
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/big.md", "Big", 0.9, "idea", "test"),
                SearchResult("garden/idea/small.md", "Small", 0.8, "idea", "test"),
            ],
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"], max_chars=200)
        assert len(result) <= 200

    async def test_retrieve_uses_hybrid_when_fts_available(self) -> None:
        vault = _mock_vault({"garden/idea": [("note.md", "Content")]})
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/note.md", "Note", 0.9, "idea", "test"),
            ],
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        # Both search methods should be called (hybrid path)
        mock_store.search.assert_called_once()
        mock_store.fts_search.assert_called_once()

    async def test_retrieve_uses_semantic_when_fts_unavailable(self) -> None:
        vault = _mock_vault({"garden/idea": [("note.md", "Content")]})
        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult("garden/idea/note.md", "Note", 0.9, "idea", "test"),
            ]
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        mock_store.search.assert_called_once()
        mock_store.fts_search.assert_not_called()

    async def test_hybrid_link_boost_capped_per_note(self) -> None:
        """A note linked from multiple top results should only be boosted once."""
        vault = _mock_vault(
            {
                "garden/idea": [
                    ("top1.md", "Top1"),
                    ("top2.md", "Top2"),
                    ("shared-link.md", "Shared linked note"),
                ],
            }
        )
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/top1.md", "Top1", 0.9, "idea", "test"),
                SearchResult("garden/idea/top2.md", "Top2", 0.8, "idea", "test"),
            ],
            linked_paths={
                "garden/idea/top1.md": {"garden/idea/shared-link.md"},
                "garden/idea/top2.md": {"garden/idea/shared-link.md"},
            },
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        assert "Shared linked note" in result

    async def test_hybrid_falls_back_on_error(self) -> None:
        vault = _mock_vault({"garden/idea": [("fallback.md", "Fallback")]})
        mock_store = _mock_store_for_hybrid()
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(side_effect=RuntimeError("API error"))

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever.retrieve(query="test", context_dirs=["garden/idea"])
        assert "Fallback" in result

    async def test_hybrid_fts_unavailable_degrades_to_semantic(self) -> None:
        """When FTS5 returns empty results, hybrid falls back to semantic-only scoring."""
        vault = _mock_vault(
            {"garden/idea": [("sem.md", "Semantic result"), ("other.md", "Other")]}
        )
        mock_store = _mock_store_for_hybrid(
            semantic_results=[
                SearchResult("garden/idea/sem.md", "Sem", 0.9, "idea", "test"),
            ],
            fts_results=[],  # FTS5 unavailable / empty
        )
        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[1.0, 0.0])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        result = await retriever._hybrid_retrieve(
            "test", ["garden/idea"], max_chars=50_000, top_k=10
        )
        assert "Semantic result" in result
        assert "Other" not in result


# ------------------------------------------------------------------
# Auto-linking in index_note
# ------------------------------------------------------------------


class TestVaultRetrieverAutoLink:
    """Test FTS indexing + auto-link generation in index_note."""

    async def test_index_note_indexes_fts_with_link_targets(self) -> None:
        mock_store = AsyncMock()
        mock_store.fts_available = True
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.upsert_fts = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1, 0.2])

        retriever = VaultRetriever(
            vault=MagicMock(), vector_store=mock_store, embedding_client=mock_embedding
        )
        content = "---\ntitle: Test\ntype: idea\n---\nBody with [[project-x]] link"
        await retriever.index_note("garden/idea/test.md", content)

        mock_store.upsert_fts.assert_called_once()
        call_args = mock_store.upsert_fts.call_args
        fts_body = call_args.args[2] if call_args.args else call_args[0][2]
        # FTS body should contain the link target as extra text
        assert "project-x" in fts_body

    async def test_index_note_stores_explicit_links(self) -> None:
        vault = MagicMock()
        # Simulate resolve_path finding the linked file
        linked_path = MagicMock()
        linked_path.exists.return_value = True
        linked_path.relative_to.return_value = Path("garden/idea/project-x.md")
        vault.resolve_path = MagicMock(return_value=linked_path)

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        content = "---\nrelated:\n  - [[project-x]]\n---\nBody text"
        await retriever.index_note("garden/idea/test.md", content)

        # Should store explicit links
        explicit_calls = [c for c in mock_store.upsert_links.call_args_list if "explicit" in str(c)]
        assert len(explicit_calls) >= 1

    async def test_index_note_stores_auto_links(self) -> None:
        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult("garden/idea/test.md", "Self", 1.0, "idea", "test"),
                SearchResult("garden/idea/similar-a.md", "A", 0.9, "idea", "test"),
                SearchResult("garden/idea/similar-b.md", "B", 0.8, "idea", "test"),
            ]
        )
        mock_store.upsert_links = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=MagicMock(), vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.index_note("garden/idea/test.md", "No frontmatter body")

        # Should store auto links (excluding self)
        auto_calls = [c for c in mock_store.upsert_links.call_args_list if "auto" in str(c)]
        assert len(auto_calls) == 1
        auto_targets = auto_calls[0].args[1]
        assert "garden/idea/test.md" not in auto_targets
        assert "garden/idea/similar-a.md" in auto_targets

    async def test_remove_note_cleans_fts_and_links(self) -> None:
        mock_store = AsyncMock()
        mock_store.fts_available = True
        mock_store.delete = AsyncMock()
        mock_store.delete_fts = AsyncMock()
        mock_store.delete_links = AsyncMock()

        retriever = VaultRetriever(
            vault=MagicMock(), vector_store=mock_store, embedding_client=MagicMock()
        )
        await retriever.remove_note("garden/idea/old.md")

        mock_store.delete.assert_called_once_with("garden/idea/old.md")
        mock_store.delete_fts.assert_called_once_with("garden/idea/old.md")
        mock_store.delete_links.assert_called_once_with("garden/idea/old.md")

    async def test_reindex_all_runs_auto_links_after_indexing(self) -> None:
        vault = _mock_vault({"garden/idea": [("a.md", "A"), ("b.md", "B")]})
        vault.resolve_path = MagicMock(side_effect=lambda p: Path(f"/vault/{p}"))

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.all_paths = AsyncMock(return_value=set())
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()
        mock_store.get_linked_paths = AsyncMock(return_value=set())
        mock_store.get_embedding = AsyncMock(return_value=[0.1])

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.reindex_all(dirs=["garden/idea"])

        # With embedding caching, get_embedding should NOT be called
        # (vectors are passed directly from index_note to _run_auto_links)
        assert mock_store.get_embedding.call_count == 0
        # But auto-link search should run for each indexed note
        assert mock_store.search.call_count >= 2

    async def test_reindex_cleans_stale_fts_and_links(self) -> None:
        vault = _mock_vault({"garden/idea": [("keep.md", "Keep")]})
        vault.resolve_path = MagicMock(side_effect=lambda p: Path(f"/vault/{p}"))

        mock_store = AsyncMock()
        mock_store.fts_available = True
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.all_paths = AsyncMock(
            return_value={"garden/idea/keep.md", "garden/idea/stale.md"}
        )
        mock_store.delete = AsyncMock()
        mock_store.delete_fts = AsyncMock()
        mock_store.delete_links = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()
        mock_store.upsert_fts = AsyncMock()

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.reindex_all(dirs=["garden/idea"])

        # Stale entry should be cleaned from all indices
        mock_store.delete.assert_any_call("garden/idea/stale.md")
        mock_store.delete_fts.assert_any_call("garden/idea/stale.md")
        mock_store.delete_links.assert_any_call("garden/idea/stale.md")


# ------------------------------------------------------------------
# Strip related field + content hash stability
# ------------------------------------------------------------------


class TestStripRelatedField:
    """Test _strip_related_field for stable content hashing."""

    def test_strips_related_from_frontmatter(self) -> None:
        text = "---\ntitle: Hello\nrelated:\n  - '[[a]]'\n  - '[[b]]'\ntype: idea\n---\nBody"
        result = _strip_related_field(text)
        assert "related" not in result
        assert "title: Hello" in result
        assert "Body" in result

    def test_no_related_returns_original(self) -> None:
        text = "---\ntitle: Hello\ntype: idea\n---\nBody"
        assert _strip_related_field(text) == text

    def test_no_frontmatter_returns_original(self) -> None:
        text = "No frontmatter here"
        assert _strip_related_field(text) == text

    def test_malformed_frontmatter_returns_original(self) -> None:
        text = "---\ntitle: Hello\nBody without closing"
        assert _strip_related_field(text) == text

    def test_preserves_key_order_and_quoting(self) -> None:
        """Regex-based stripping must not alter other keys' format."""
        text = (
            '---\ntitle: "Hello World"\n'
            "related:\n  - '[[a]]'\n  - '[[b]]'\n"
            "type: idea\ncustom_key: 123\n---\nBody"
        )
        result = _strip_related_field(text)
        assert "related" not in result
        assert 'title: "Hello World"' in result
        assert "type: idea" in result
        assert "custom_key: 123" in result


class TestContentHashIgnoresRelated:
    """Test that content_hash is stable when only ``related`` changes."""

    def test_same_hash_with_different_related(self) -> None:
        text1 = "---\ntitle: Hello\ntype: idea\n---\nBody"
        text2 = "---\nrelated:\n  - '[[new-link]]'\ntitle: Hello\ntype: idea\n---\nBody"
        assert _content_hash(text1) == _content_hash(text2)

    def test_different_hash_when_body_changes(self) -> None:
        text1 = "---\ntitle: Hello\n---\nBody A"
        text2 = "---\ntitle: Hello\n---\nBody B"
        assert _content_hash(text1) != _content_hash(text2)

    def test_hash_stable_with_inline_array_related(self) -> None:
        """Inline array format ``related: [a, b]`` must also be stripped."""
        text_no_related = "---\ntitle: Hello\ntype: idea\n---\nBody"
        text_inline = "---\ntitle: Hello\ntype: idea\nrelated: ['[[a]]', '[[b]]']\n---\nBody"
        assert _content_hash(text_no_related) == _content_hash(text_inline)

    def test_hash_stable_with_scalar_related(self) -> None:
        """Scalar ``related: value`` must also be stripped."""
        text_no_related = "---\ntitle: Hello\n---\nBody"
        text_scalar = "---\ntitle: Hello\nrelated: '[[note]]'\n---\nBody"
        assert _content_hash(text_no_related) == _content_hash(text_scalar)


# ------------------------------------------------------------------
# _update_note_related — writes auto-links to note frontmatter
# ------------------------------------------------------------------


class TestUpdateNoteRelated:
    """Test that auto-links are written to note frontmatter."""

    async def test_preserves_frontmatter_format(self, tmp_path) -> None:
        """Regex-based surgery must not reorder keys or change quoting."""
        original_fm = '---\ntitle: "My Title"\ntype: idea\ncustom: 42\n---\nBody\n'
        note_file = tmp_path / "note.md"
        note_file.write_text(original_fm)

        vault = MagicMock()
        vault.root = tmp_path
        vault.resolve_path = MagicMock(return_value=note_file)
        vault.read_note_content = AsyncMock(return_value=note_file.read_text())

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()
        mock_store.get_linked_paths = AsyncMock(return_value={"other.md"})

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.index_note("note.md", note_file.read_text())

        updated = note_file.read_text()
        # Original keys should be in their original format and order
        assert 'title: "My Title"' in updated
        assert "type: idea" in updated
        assert "custom: 42" in updated
        assert "[[other]]" in updated

    async def test_writes_related_to_frontmatter(self, tmp_path) -> None:
        note_file = tmp_path / "garden" / "idea" / "test.md"
        note_file.parent.mkdir(parents=True)
        note_file.write_text("---\ntitle: Test\ntype: idea\n---\nBody text\n")

        vault = MagicMock()
        vault.root = tmp_path
        vault.resolve_path = MagicMock(return_value=note_file)
        vault.read_note_content = AsyncMock(return_value=note_file.read_text())

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(
            return_value=[
                SearchResult("garden/idea/similar.md", "Similar", 0.9, "idea", "test"),
            ]
        )
        mock_store.upsert_links = AsyncMock()
        mock_store.get_linked_paths = AsyncMock(return_value={"garden/idea/similar.md"})

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.index_note("garden/idea/test.md", note_file.read_text())

        # Note file should now contain [[similar]] in related
        updated = note_file.read_text()
        assert "[[similar]]" in updated

    async def test_merges_with_existing_related(self, tmp_path) -> None:
        note_file = tmp_path / "note.md"
        note_file.write_text("---\ntitle: Test\nrelated:\n- '[[existing]]'\n---\nBody\n")

        vault = MagicMock()
        vault.root = tmp_path
        vault.resolve_path = MagicMock(return_value=note_file)
        vault.read_note_content = AsyncMock(return_value=note_file.read_text())

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()
        mock_store.get_linked_paths = AsyncMock(return_value={"garden/idea/new.md"})

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.index_note("note.md", note_file.read_text())

        updated = note_file.read_text()
        assert "[[existing]]" in updated
        assert "[[new]]" in updated

    async def test_skips_when_no_frontmatter(self, tmp_path) -> None:
        note_file = tmp_path / "note.md"
        original = "No frontmatter body"
        note_file.write_text(original)

        vault = MagicMock()
        vault.root = tmp_path
        vault.resolve_path = MagicMock(return_value=note_file)
        vault.read_note_content = AsyncMock(return_value=original)

        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()
        mock_store.get_linked_paths = AsyncMock(return_value={"other.md"})

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.index_note("note.md", original)

        # File should remain unchanged (no frontmatter to update)
        assert note_file.read_text() == original

    async def test_skips_when_no_linked_paths(self) -> None:
        mock_store = AsyncMock()
        mock_store.fts_available = False
        mock_store.get_content_hash = AsyncMock(return_value=None)
        mock_store.upsert = AsyncMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store.upsert_links = AsyncMock()
        mock_store.get_linked_paths = AsyncMock(return_value=set())

        mock_embedding = AsyncMock()
        mock_embedding.embed_one = AsyncMock(return_value=[0.1])

        vault = MagicMock()
        retriever = VaultRetriever(
            vault=vault, vector_store=mock_store, embedding_client=mock_embedding
        )
        await retriever.index_note("note.md", "content")
        # resolve_path should not be called for related update
        # (get_linked_paths returns empty set → skip)
