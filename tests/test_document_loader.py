"""
Tests for the canonical ``DocumentLoader`` in ``db.document_loader``.

These tests are intentionally pure (no Docker, no testcontainers): they exercise
file discovery and chunking on a ``tmp_path`` and verify the module-level
delegates are behaviorally equivalent to the class.
"""

import sys
from pathlib import Path

from langchain_core.documents import Document


sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from db.document_loader import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    SUPPORTED_SUFFIXES,
    DocumentLoader,
    chunk_document,
    chunk_documents,
    discover_documents,
)


class TestDiscovery:
    """Document discovery rules via the ``DocumentLoader`` class and delegate."""

    def test_discovers_supported_files_sorted_and_skips_hidden(self, tmp_path):
        (tmp_path / "a.md").write_text("# titulo", encoding="utf-8")
        (tmp_path / "b.txt").write_text("texto", encoding="utf-8")
        (tmp_path / ".hidden.md").write_text("secreto", encoding="utf-8")
        (tmp_path / "c.markdown").write_text("# unsupported", encoding="utf-8")

        discovered = DocumentLoader(tmp_path).discover()

        assert sorted(discovered) == discovered
        assert [path.name for path in discovered] == ["a.md", "b.txt"]

    def test_missing_directory_returns_empty(self, tmp_path):
        assert DocumentLoader(tmp_path / "does-not-exist").discover() == []
        assert discover_documents(tmp_path / "does-not-exist") == []


class TestChunking:
    """Chunking behavior on ``.md`` and ``.txt`` inputs."""

    def test_chunk_markdown_headers_and_metadata(self, tmp_path):
        body = ("Cobertura mecánica completa. " * 60) + "\n## Exclusiones\n\n" + (
            "No cubre accidentes. " * 60
        )
        content = "# Garantía\n\n" + body
        path = tmp_path / "warranty.md"
        path.write_text(content, encoding="utf-8")

        chunks = DocumentLoader.chunk(path)

        assert chunks
        assert all(isinstance(chunk, Document) for chunk in chunks)
        assert all(chunk.metadata["source"] == "warranty.md" for chunk in chunks)
        assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))

    def test_chunk_txt(self, tmp_path):
        path = tmp_path / "doc.txt"
        path.write_text("contenido " * 120, encoding="utf-8")

        chunks = DocumentLoader.chunk(path)

        assert chunks
        assert all(chunk.metadata["source"] == "doc.txt" for chunk in chunks)
        assert [chunk.metadata["chunk_index"] for chunk in chunks] == list(range(len(chunks)))


class TestRobustness:
    """Edge cases around malformed input."""

    def test_chunk_unreadable_returns_empty(self, tmp_path):
        path = tmp_path / "broken.txt"
        path.write_bytes(b"\xff\xfe\x00\xfd")

        chunks = DocumentLoader.chunk(path)

        assert chunks == []


class TestDelegatesEquivalentToClass:
    """The module-level functions must delegate to the canonical class."""

    def test_chunk_document_matches_class(self, tmp_path):
        path = tmp_path / "doc.md"
        path.write_text("# Title\n\nContenido de prueba. " * 50, encoding="utf-8")

        assert chunk_document(path) == DocumentLoader.chunk(path)

    def test_chunk_documents_matches_class_concatenation(self, tmp_path):
        first = tmp_path / "a.txt"
        first.write_text("primer documento " * 10, encoding="utf-8")
        second = tmp_path / "b.md"
        second.write_text("# Segundo\n\nContenido del segundo. " * 10, encoding="utf-8")

        assert chunk_documents([first, second]) == DocumentLoader.chunk(first) + DocumentLoader.chunk(
            second
        )

    def test_discover_documents_matches_class(self, tmp_path):
        (tmp_path / "a.md").write_text("# a", encoding="utf-8")
        (tmp_path / "b.txt").write_text("b", encoding="utf-8")

        assert discover_documents(tmp_path) == DocumentLoader(tmp_path).discover()


class TestConstantsContract:
    """Public constants are part of the module's contract."""

    def test_chunk_constants(self):
        assert CHUNK_SIZE == 500
        assert CHUNK_OVERLAP == 100
        assert SUPPORTED_SUFFIXES == (".md", ".txt")
