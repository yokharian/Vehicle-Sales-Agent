"""
Tests for the document search tool and retrieval stack.
"""

import os
import sys
from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import DeterministicFakeEmbedding
from pydantic import ValidationError
from sqlalchemy import delete


sys.path.append(str(Path(__file__).parent.parent / "src"))

import db.database as db_module
from config import DocumentSearchSettings
from tools.document_search import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DocumentChunk,
    DocumentChunkResult,
    DocumentSearchError,
    DocumentSearchInput,
    build_bm25_retriever,
    build_hybrid_retriever,
    chunk_document,
    chunk_documents,
    dense_search,
    discover_documents,
    document_search_tool,
    ensure_tables,
    load_chunks,
    reindex,
    resolve_embeddings,
)


FAKE_EMBEDDINGS = DeterministicFakeEmbedding(size=768)

SEED_CHUNKS = [
    Document(
        page_content="La tasa de interés anual para financiamiento es del 10%. El plazo puede ser de 3, 4, 5 o 6 años.",
        metadata={"source": "financing.md", "chunk_index": 0},
    ),
    Document(
        page_content="El enganche se resta del precio del vehículo para obtener el monto financiado.",
        metadata={"source": "financing.md", "chunk_index": 1},
    ),
    Document(
        page_content="Se requiere identificación oficial vigente, comprobante de domicilio y comprobantes de ingresos.",
        metadata={"source": "requirements.txt", "chunk_index": 0},
    ),
    Document(
        page_content="El cliente debe ser mayor de 18 años y contar con CURP actualizada.",
        metadata={"source": "requirements.txt", "chunk_index": 1},
    ),
    Document(
        page_content="La garantía mecánica cubre 3 meses o 3,000 kilómetros, lo que ocurra primero.",
        metadata={"source": "warranty.md", "chunk_index": 0},
    ),
    Document(
        page_content="La garantía no cubre daños por accidentes ni el desgaste natural de frenos y llantas.",
        metadata={"source": "warranty.md", "chunk_index": 1},
    ),
]


@pytest.fixture
def document_index():
    """Seed the shared pgvector container with a deterministic chunk index."""
    ensure_tables()
    reindex(SEED_CHUNKS, FAKE_EMBEDDINGS)
    yield FAKE_EMBEDDINGS


class TestDocumentDiscovery:
    """Test document discovery rules."""

    def test_discovers_supported_files_sorted(self, tmp_path):
        (tmp_path / "b.txt").write_text("texto", encoding="utf-8")
        (tmp_path / "a.md").write_text("# titulo", encoding="utf-8")

        discovered = discover_documents(tmp_path)

        assert [path.name for path in discovered] == ["a.md", "b.txt"]

    def test_ignores_hidden_and_unsupported_files(self, tmp_path):
        (tmp_path / ".hidden.md").write_text("secreto", encoding="utf-8")
        (tmp_path / "notes.json").write_text("{}", encoding="utf-8")
        (tmp_path / "report.pdf").write_bytes(b"%PDF")
        (tmp_path / "doc.md").write_text("contenido", encoding="utf-8")

        discovered = discover_documents(tmp_path)

        assert [path.name for path in discovered] == ["doc.md"]

    def test_missing_directory_returns_empty(self, tmp_path):
        assert discover_documents(tmp_path / "does-not-exist") == []


class TestChunking:
    """Test chunk sizes, overlap, and metadata integrity."""

    def test_chunks_respect_size_limit(self, tmp_path):
        long_text = "palabra " * 200
        (tmp_path / "long.txt").write_text(long_text, encoding="utf-8")

        chunks = chunk_document(tmp_path / "long.txt")

        assert len(chunks) > 1
        assert all(len(chunk.page_content) <= CHUNK_SIZE for chunk in chunks)
        assert any(len(chunks[i].page_content) for i in range(len(chunks)))

    def test_chunk_overlap_between_consecutive_chunks(self, tmp_path):
        sentence = "la garantia cubre motor y transmision principales. "
        (tmp_path / "overlap.txt").write_text(sentence * 20, encoding="utf-8")

        chunks = chunk_document(tmp_path / "overlap.txt")

        assert len(chunks) > 1
        assert CHUNK_OVERLAP > 0
        later_starts = [chunk.metadata["chunk_index"] for chunk in chunks]
        assert later_starts == list(range(len(chunks)))

    def test_markdown_headings_preserved_and_chunked(self, tmp_path):
        content = (
            "# Garantía\n\n"
            + ("Cobertura mecánica completa. " * 60)
            + "\n## Exclusiones\n\n"
            + ("No cubre accidentes. " * 60)
        )
        (tmp_path / "warranty.md").write_text(content, encoding="utf-8")

        chunks = chunk_document(tmp_path / "warranty.md")

        assert len(chunks) > 2
        assert all(len(chunk.page_content) <= CHUNK_SIZE for chunk in chunks)
        assert any("Garantía" in chunk.page_content for chunk in chunks)
        assert any("Exclusiones" in chunk.page_content for chunk in chunks)

    def test_metadata_integrity(self, tmp_path):
        (tmp_path / "doc.txt").write_text("contenido " * 120, encoding="utf-8")

        chunks = chunk_document(tmp_path / "doc.txt")

        for expected_index, chunk in enumerate(chunks):
            assert chunk.metadata["source"] == "doc.txt"
            assert chunk.metadata["chunk_index"] == expected_index
            assert set(chunk.metadata) == {"source", "chunk_index"}

    def test_unreadable_document_skipped(self, tmp_path):
        unreadable = tmp_path / "broken.txt"
        unreadable.write_bytes(b"\xff\xfe\xfa")

        chunks = chunk_document(unreadable)

        assert chunks == []

    def test_chunk_documents_preserves_source_order(self, tmp_path):
        (tmp_path / "z.md").write_text("# uno", encoding="utf-8")
        (tmp_path / "a.txt").write_text("dos", encoding="utf-8")

        chunks = chunk_documents(discover_documents(tmp_path))

        assert [chunk.metadata["source"] for chunk in chunks] == ["a.txt", "z.md"]


class TestEmbeddingProviderConfig:
    """Test provider selection through configuration."""

    def test_openai_embeddings_resolved(self, monkeypatch):
        monkeypatch.delenv("DOCUMENT_EMBEDDING_PROVIDER", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "test-key-for-testing")

        embeddings = resolve_embeddings()

        assert type(embeddings).__name__ == "OpenAIEmbeddings"

    def test_openrouter_embeddings_resolved(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_EMBEDDING_PROVIDER", "openrouter")
        monkeypatch.delenv("DOCUMENT_EMBEDDING_MODEL", raising=False)
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

        embeddings = resolve_embeddings()

        assert type(embeddings).__name__ == "OpenAIEmbeddings"
        assert embeddings.openai_api_base == "https://openrouter.ai/api/v1"
        assert embeddings.model == "openai/text-embedding-3-small"

    def test_openrouter_requires_api_key(self, monkeypatch):
        monkeypatch.setenv("DOCUMENT_EMBEDDING_PROVIDER", "openrouter")
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
            resolve_embeddings()


@pytest.mark.usefixtures("document_index")
class TestDocumentStore:
    """Test pgvector persistence and dense retrieval."""

    def test_reindex_and_load_roundtrip(self):
        loaded = load_chunks()

        assert len(loaded) == len(SEED_CHUNKS)
        assert [(doc.metadata["source"], doc.metadata["chunk_index"]) for doc in loaded] == [
            (doc.metadata["source"], doc.metadata["chunk_index"]) for doc in SEED_CHUNKS
        ]
        assert all(
            doc.page_content == original.page_content
            for doc, original in zip(loaded, SEED_CHUNKS, strict=True)
        )

    def test_dense_search_returns_metadata(self, document_index):
        results = dense_search("tasa", document_index, limit=3)

        assert 1 <= len(results) <= 3
        for document in results:
            assert document.metadata["source"] in {
                "financing.md",
                "requirements.txt",
                "warranty.md",
            }
            assert isinstance(document.metadata["chunk_index"], int)

    def test_dense_search_deterministic_ordering(self, document_index):
        first = dense_search("garantía mecánica", document_index, limit=4)
        second = dense_search("garantía mecánica", document_index, limit=4)

        assert first == second

    def test_reindex_replaces_previous_index(self, document_index):
        replacement = [SEED_CHUNKS[0]]
        reindex(replacement, document_index)

        loaded = load_chunks()

        assert len(loaded) == 1
        assert loaded[0].metadata["source"] == "financing.md"


@pytest.mark.usefixtures("document_index")
class TestBM25Retrieval:
    """Test lexical retrieval over the indexed corpus."""

    def test_exact_term_retrieval(self):
        chunks = load_chunks()
        retriever = build_bm25_retriever(chunks, candidates=3)

        hits = retriever.invoke("tasa 10%")

        assert hits
        assert hits[0].metadata["source"] == "financing.md"

    def test_keyword_retrieval_for_requirements(self):
        chunks = load_chunks()
        retriever = build_bm25_retriever(chunks, candidates=3)

        hits = retriever.invoke("identificación oficial comprobante")

        assert hits
        assert hits[0].metadata["source"] == "requirements.txt"


class TestHybridRetrieval:
    """Test ensemble retrieval combining BM25 and dense search."""

    def test_hybrid_returns_corpus_documents_only(self, document_index):
        chunks = load_chunks()
        settings = DocumentSearchSettings(
            top_k=4, bm25_candidates=3, dense_candidates=3, bm25_weight=0.5
        )
        retriever = build_hybrid_retriever(chunks, document_index, settings)

        results = retriever.invoke("¿Qué documentos necesito para comprar?")

        assert results
        assert len(results) <= settings.bm25_candidates + settings.dense_candidates
        expected = {(doc.metadata["source"], doc.metadata["chunk_index"]) for doc in chunks}
        for document in results:
            assert (document.metadata["source"], document.metadata["chunk_index"]) in expected

    def test_hybrid_ordering_is_deterministic(self, document_index):
        chunks = load_chunks()
        settings = DocumentSearchSettings(
            top_k=4, bm25_candidates=3, dense_candidates=3, bm25_weight=0.5
        )
        retriever = build_hybrid_retriever(chunks, document_index, settings)

        first = retriever.invoke("tasa de interés")
        second = retriever.invoke("tasa de interés")

        assert [(doc.metadata["source"], doc.metadata["chunk_index"]) for doc in first] == [
            (doc.metadata["source"], doc.metadata["chunk_index"]) for doc in second
        ]


class TestDocumentSearchTool:
    """Test the document_search tool contract."""

    def test_tool_attributes(self):
        assert document_search_tool.name == "document_search"
        assert "knowledge" in document_search_tool.description.lower()
        assert document_search_tool.args_schema is not None
        assert callable(document_search_tool.func)

    def test_input_schema_validation(self):
        validated = DocumentSearchInput(query="¿Cómo funciona el financiamiento?")
        assert validated.k == 6

        with pytest.raises(ValidationError):
            DocumentSearchInput(query="", k=6)

        with pytest.raises(ValidationError):
            DocumentSearchInput(query="test", k=0)

        with pytest.raises(ValidationError):
            DocumentSearchInput(query="test", k=21)

    def test_query_validation_before_retrieval(self):
        with pytest.raises(ValueError, match="query"):
            document_search_tool.func(query="   ", k=6)

    @pytest.mark.usefixtures("document_index")
    def test_successful_retrieval_contract(self, monkeypatch):
        monkeypatch.setattr("tools.document_search.resolve_embeddings", lambda: FAKE_EMBEDDINGS)

        summary, results = document_search_tool.func(
            query="tasa de interés del financiamiento", k=3
        )

        assert isinstance(summary, str)
        assert len(summary) > 0
        assert 1 <= len(results) <= 3
        for result in results:
            assert isinstance(result, DocumentChunkResult)
            assert result.content
            assert result.metadata.source in {"financing.md", "requirements.txt", "warranty.md"}
            assert result.metadata.chunk_index >= 0

    @pytest.mark.usefixtures("document_index")
    def test_empty_document_index_returns_empty_results(self):
        with db_module.get_session_sync() as session:
            session.execute(delete(DocumentChunk))
            session.commit()

        summary, results = document_search_tool.func(query="¿Qué ofrece Kavak?", k=6)

        assert summary == ""
        assert results == []

    @pytest.mark.usefixtures("document_index")
    def test_embedding_failure_returns_controlled_error(self, monkeypatch):
        def _broken_embeddings():
            raise RuntimeError("connection refused")

        monkeypatch.setattr("tools.document_search.resolve_embeddings", _broken_embeddings)

        with pytest.raises(DocumentSearchError, match="temporarily unavailable") as exc_info:
            document_search_tool.func(query="garantía", k=6)

        assert "connection" not in str(exc_info.value)
        assert os.getenv("DATABASE_URL") not in str(exc_info.value)

    @pytest.mark.usefixtures("document_index")
    def test_retrieval_failure_returns_controlled_error(self, monkeypatch):
        def _broken_retriever(*args, **kwargs):  # noqa: ARG001 - failure stub
            raise ValueError("boom")

        monkeypatch.setattr("tools.document_search.build_hybrid_retriever", _broken_retriever)

        with pytest.raises(DocumentSearchError, match="temporarily unavailable"):
            document_search_tool.func(query="garantía", k=6)
