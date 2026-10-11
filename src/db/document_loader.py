"""
Loading, chunking, and persistence of approved knowledge-base documents.

The :class:`DocumentLoader` class is the single API for loading and chunking
approved knowledge-base documents, and the storage primitives below it keep
every ``document_chunks`` SQL statement in one place: reindex, per-source
upsert, purge, and the reader queries.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy import Text, UniqueConstraint, delete, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import db.database as db_module
from config import DocumentSearchSettings


if TYPE_CHECKING:
    from sqlalchemy import Delete


logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = (".md", ".txt")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
_MARKDOWN_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


def _document(page_content: str, source: str, chunk_index: int) -> Document:
    """Build one chunk document with the canonical provenance metadata."""
    return Document(
        page_content=page_content, metadata={"source": source, "chunk_index": chunk_index}
    )


def content_hash(model_id: str, page_content: str) -> str:
    """Model-qualified chunk hash; an embedding-model change invalidates skips."""
    return hashlib.sha256(f"{model_id}\x00{page_content}".encode()).hexdigest()


class DocumentLoader:
    """Read and chunk the approved knowledge-base documents for retrieval."""

    def __init__(self, documents_path: str | Path) -> None:
        """Remember the directory to scan; parsing is lazy."""
        self.documents_path = Path(documents_path)

    def discover(self) -> list[Path]:
        """List supported, non-hidden documents in sorted order."""
        directory = self.documents_path
        if not directory.is_dir():
            return []
        return sorted(
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_SUFFIXES
            and not path.name.startswith(".")
        )

    @staticmethod
    def chunk(path: Path) -> list[Document]:
        """Read one document and split it into indexed chunks."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            logger.warning("Skipping unreadable document %s: %s", path.name, type(exc).__name__)
            return []

        if path.suffix.lower() == ".md":
            sections = MarkdownHeaderTextSplitter(
                headers_to_split_on=_MARKDOWN_HEADERS,
                strip_headers=False,
            ).split_text(text)
            section_texts = [section.page_content for section in sections]
        else:
            section_texts = [text]

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        pieces = [piece for section in section_texts for piece in splitter.split_text(section)]
        return [_document(piece, path.name, index) for index, piece in enumerate(pieces)]


class _DocumentBase(DeclarativeBase):
    pass


class DocumentChunk(_DocumentBase):
    """One retrieval chunk with its embedding vector."""

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("source", "chunk_index", name="uq_chunk_position"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str]
    chunk_index: Mapped[int]
    content: Mapped[str]
    # Dim-free vector column: any embedding model can be indexed; the full
    # replace on re-index keeps a single vector space per index.
    embedding = mapped_column(Vector())
    content_hash: Mapped[str | None] = mapped_column(Text, nullable=True)


def ensure_tables() -> None:
    """Create the document table if it does not exist yet.

    The pgvector extension is enabled idempotently before ``create_all`` so the
    ``VECTOR`` column type resolves on a fresh database. On the live Supabase
    instance pgvector is already pre-enabled, so the statement is a no-op.
    ``create_all`` already provisions ``content_hash`` on a fresh database; for
    pre-existing tables (e.g. the live Supabase instance) the follow-up
    ``ALTER TABLE ... ADD COLUMN IF NOT EXISTS`` is a no-op once the column is
    present, keeping the upgrade additive and idempotent.
    """
    with db_module.pgvector_engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    _DocumentBase.metadata.create_all(db_module.pgvector_engine)
    with db_module.pgvector_engine.begin() as conn:
        conn.execute(text("ALTER TABLE document_chunks ADD COLUMN IF NOT EXISTS content_hash TEXT"))


def _row_document(row: DocumentChunk) -> Document:
    return _document(row.content, row.source, row.chunk_index)


def _chunk_rows(
    chunks: list[Document], vectors: list, source: str | None = None
) -> list[DocumentChunk]:
    """Build ORM rows with model-qualified content hashes.

    ``source`` overrides chunk metadata when the caller already knows the
    single source (per-file upsert); whole-corpus reindex keeps per-chunk
    metadata sources.
    """
    model_id = DocumentSearchSettings().resolved_embedding_model
    return [
        DocumentChunk(
            source=chunk.metadata["source"] if source is None else source,
            chunk_index=chunk.metadata["chunk_index"],
            content=chunk.page_content,
            embedding=vector,
            content_hash=content_hash(model_id, chunk.page_content),
        )
        for chunk, vector in zip(chunks, vectors, strict=True)
    ]


def _replace_rows(delete_statement: Delete, rows: list[DocumentChunk]) -> None:
    """Delete then insert in ONE short transaction, atomic for readers."""
    with db_module.get_pgvector_session_sync() as session:
        session.execute(delete_statement)
        session.add_all(rows)
        session.commit()


def reindex(chunks: list[Document], embeddings) -> int:
    """Replace the whole index with the given chunks, embedded and stored."""
    ensure_tables()
    vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks]) if chunks else []
    _replace_rows(delete(DocumentChunk), _chunk_rows(chunks, vectors))
    return len(chunks)


def upsert_document_chunks(source: str, chunks: list[Document], embeddings) -> int:
    """Replace the stored chunks of one source in a single short transaction.

    Embedding runs before the transaction opens so the write lock window stays
    short. Returns the number of chunks stored for ``source``.
    """
    vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks]) if chunks else []
    _replace_rows(
        delete(DocumentChunk).where(DocumentChunk.source == source),
        _chunk_rows(chunks, vectors, source=source),
    )
    return len(chunks)


def purge_removed_sources(active_sources: set[str]) -> int:
    """Delete chunks for sources no longer present in ``active_sources``.

    An empty active set purges every stored chunk. Returns the deleted count.
    """
    with db_module.get_pgvector_session_sync() as session:
        if active_sources:
            result = session.execute(
                delete(DocumentChunk).where(DocumentChunk.source.not_in(active_sources))
            )
        else:
            result = session.execute(delete(DocumentChunk))
        deleted = result.rowcount
        session.commit()
    return deleted


def load_chunks() -> list[Document]:
    """Load every stored chunk in deterministic source order."""
    with db_module.get_pgvector_session_sync() as session:
        rows = (
            session.query(DocumentChunk)
            .order_by(DocumentChunk.source, DocumentChunk.chunk_index)
            .all()
        )
        return [_row_document(row) for row in rows]


def dense_search(query: str, embeddings, limit: int) -> list[Document]:
    """Retrieve chunks by cosine similarity against the query embedding."""
    query_vector = embeddings.embed_query(query)
    with db_module.get_pgvector_session_sync() as session:
        rows = (
            session.query(DocumentChunk)
            .order_by(
                DocumentChunk.embedding.cosine_distance(query_vector),
                DocumentChunk.source,
                DocumentChunk.chunk_index,
            )
            .limit(limit)
            .all()
        )
        return [_row_document(row) for row in rows]


def stored_chunk_hashes(source: str) -> list[tuple[int, str | None]]:
    """Return the stored (chunk_index, content_hash) pairs of one source."""
    with db_module.get_pgvector_session_sync() as session:
        rows = (
            session.query(DocumentChunk.chunk_index, DocumentChunk.content_hash)
            .filter(DocumentChunk.source == source)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )
    return [(row.chunk_index, row.content_hash) for row in rows]
