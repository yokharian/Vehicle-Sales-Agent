"""
LangChain tool for grounded knowledge retrieval over the approved knowledge base.

Approved `.md` and `.txt` documents are indexed explicitly into PostgreSQL +
pgvector (chunking, embedding, storage), and retrieved with a hybrid BM25 +
dense ensemble. The tool returns evidence passages with source metadata; it
never generates answers, and empty or failed retrieval is reported as such so
the agent cannot fabricate business facts.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import rank_bm25
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import tool
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pgvector.sqlalchemy import Vector
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import UniqueConstraint, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

import db.database as db_module
from config import DEFAULT_EMBEDDING_MODELS, DocumentSearchSettings


if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = (".md", ".txt")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
_MARKDOWN_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


DEFAULT_TOP_K = 6
DEFAULT_CANDIDATES = 6
DEFAULT_BM25_WEIGHT = 0.5
MIN_K = 1
MAX_K = 20


class DocumentSearchError(RuntimeError):
    """Raised when retrieval fails, without leaking connection details."""


class DocumentSearchInput(BaseModel):
    """Input schema for knowledge base search."""

    query: str = Field(min_length=1, description="Natural-language question in Spanish or English")
    k: int = Field(
        default=6,
        description=f"Maximum number of passages to retrieve ({MIN_K}-{MAX_K})",
        ge=MIN_K,
        le=MAX_K,
    )


class DocumentChunkMetadata(BaseModel):
    """Provenance metadata for a retrieved passage."""

    source: str
    chunk_index: int


class DocumentChunkResult(BaseModel):
    """One retrieved evidence passage."""

    content: str
    metadata: DocumentChunkMetadata


def discover_documents(documents_dir: str | Path) -> list[Path]:
    """List supported, non-hidden documents in sorted order."""
    directory = Path(documents_dir)
    if not directory.is_dir():
        return []
    return sorted(
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and not path.name.startswith(".")
    )


def chunk_document(path: Path) -> list[Document]:
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

    splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    chunks = [
        Document(page_content=piece, metadata={"source": path.name})
        for section in section_texts
        for piece in splitter.split_text(section)
    ]
    for chunk_index, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = chunk_index
    return chunks


def chunk_documents(paths: list[Path]) -> list[Document]:
    """Chunk every discovered document, keeping deterministic source order."""
    return [chunk for path in paths for chunk in chunk_document(path)]


def resolve_provider() -> str:
    """Read the configured embedding provider name."""
    settings = DocumentSearchSettings()
    if settings.embedding_provider not in DEFAULT_EMBEDDING_MODELS:
        raise ValueError(
            f"Unknown embedding provider {settings.embedding_provider!r}; "
            f"expected one of {list(DEFAULT_EMBEDDING_MODELS)}"
        )
    return settings.embedding_provider


def resolve_embeddings():
    """Build the configured embedding model for indexing and querying."""
    settings = DocumentSearchSettings()
    model = settings.resolved_embedding_model
    if settings.embedding_provider == "openai":
        return OpenAIEmbeddings(model=model)
    return GoogleGenerativeAIEmbeddings(model=model)


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


def ensure_tables() -> None:
    """Create the document table if it does not exist yet."""
    _DocumentBase.metadata.create_all(db_module.engine)


def _row_document(row: DocumentChunk) -> Document:
    return Document(
        page_content=row.content,
        metadata={"source": row.source, "chunk_index": row.chunk_index},
    )


def reindex(chunks: list[Document], embeddings) -> int:
    """Replace the whole index with the given chunks, embedded and stored."""
    ensure_tables()
    vectors = embeddings.embed_documents([chunk.page_content for chunk in chunks]) if chunks else []
    with db_module.get_session_sync() as session:
        session.execute(delete(DocumentChunk))
        session.add_all(
            DocumentChunk(
                source=chunk.metadata["source"],
                chunk_index=chunk.metadata["chunk_index"],
                content=chunk.page_content,
                embedding=vector,
            )
            for chunk, vector in zip(chunks, vectors, strict=True)
        )
        session.commit()
    return len(chunks)


def load_chunks() -> list[Document]:
    """Load every stored chunk in deterministic source order."""
    ensure_tables()
    with db_module.get_session_sync() as session:
        rows = (
            session.query(DocumentChunk)
            .order_by(DocumentChunk.source, DocumentChunk.chunk_index)
            .all()
        )
        return [_row_document(row) for row in rows]


def dense_search(query: str, embeddings, limit: int) -> list[Document]:
    """Retrieve chunks by cosine similarity against the query embedding."""
    query_vector = embeddings.embed_query(query)
    with db_module.get_session_sync() as session:
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


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens; deterministic across platforms and runs."""
    return re.findall(r"\w+", text.lower())


@dataclass(frozen=True)
class HybridConfig:
    """Retrieval parameters; ensemble weights must be validated against the
    retrieval evaluation dataset before being treated as final."""

    top_k: int = DEFAULT_TOP_K
    bm25_candidates: int = DEFAULT_CANDIDATES
    dense_candidates: int = DEFAULT_CANDIDATES
    bm25_weight: float = DEFAULT_BM25_WEIGHT

    @property
    def dense_weight(self) -> float:
        return 1.0 - self.bm25_weight


def resolve_hybrid_config() -> HybridConfig:
    """Read retrieval parameters from the validated application settings."""
    settings = DocumentSearchSettings()
    return HybridConfig(
        top_k=settings.top_k,
        bm25_candidates=settings.bm25_candidates,
        dense_candidates=settings.dense_candidates,
        bm25_weight=settings.bm25_weight,
    )


def build_bm25_retriever(chunks: list[Document], candidates: int) -> BM25Retriever:
    """Lexical retriever over the indexed corpus.

    BM25Plus is used instead of BM25Okapi because Okapi's IDF collapses to
    zero on small corpora, which makes every document score identically.
    """
    vectorizer = rank_bm25.BM25Plus([_tokenize(chunk.page_content) for chunk in chunks])
    return BM25Retriever(
        vectorizer=vectorizer,
        docs=chunks,
        preprocess_func=_tokenize,
        k=candidates,
    )


class DenseRetriever(BaseRetriever):
    """Semantic retriever backed by pgvector cosine distance."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    embeddings: object
    candidates: int

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,  # noqa: ARG002 - required by the retriever interface
    ) -> list[Document]:
        return dense_search(query, self.embeddings, self.candidates)


def build_hybrid_retriever(
    chunks: list[Document],
    embeddings,
    config: HybridConfig,
) -> EnsembleRetriever:
    """Combine BM25 and dense retrieval with rank fusion."""
    bm25_retriever = build_bm25_retriever(chunks, config.bm25_candidates)
    dense_retriever = DenseRetriever(embeddings=embeddings, candidates=config.dense_candidates)
    return EnsembleRetriever(
        retrievers=[bm25_retriever, dense_retriever],
        weights=[config.bm25_weight, config.dense_weight],
    )


@tool(
    "document_search",
    description="""Search the approved business knowledge base for evidence.

Retrieves relevant passages for questions about the company, purchase
requirements, financing, warranty, and other approved documentation.
Supports natural-language questions in Spanish and English.

Returns passages with their source metadata; returns no results when the
knowledge base has no relevant content.""",
    args_schema=DocumentSearchInput,
    error_on_invalid_docstring=False,
    return_direct=False,
    parse_docstring=True,
    response_format="content_and_artifact",
)
def document_search_tool(query: str, k: int = 6) -> tuple[str, list[DocumentChunkResult]]:
    if not query or not query.strip():
        raise ValueError("query must not be empty")
    clean_query = query.strip()
    effective_k = max(MIN_K, min(k, MAX_K))

    try:
        return _retrieve(clean_query, effective_k)
    except DocumentSearchError:
        raise
    except Exception as exc:
        logger.error("Document retrieval failed: %s", type(exc).__name__)
        raise DocumentSearchError("Document search is temporarily unavailable.") from exc


def _retrieve(clean_query: str, effective_k: int) -> tuple[str, list[DocumentChunkResult]]:
    indexed_chunks = load_chunks()
    if not indexed_chunks:
        logger.warning("Document index is empty; run scripts/index_documents.py before querying.")
        return "", []

    embeddings = resolve_embeddings()
    config = resolve_hybrid_config()
    documents = build_hybrid_retriever(indexed_chunks, embeddings, config).invoke(clean_query)

    results = [
        DocumentChunkResult(
            content=document.page_content,
            metadata=DocumentChunkMetadata(
                source=str(document.metadata["source"]),
                chunk_index=int(document.metadata["chunk_index"]),
            ),
        )
        for document in documents[:effective_k]
    ]
    evidence_text = "\n\n".join(
        f"<SOURCE>{result.metadata.source}</SOURCE>\n{result.content}" for result in results
    )
    return evidence_text, results
