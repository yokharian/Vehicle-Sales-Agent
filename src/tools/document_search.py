"""
LangChain tool for grounded knowledge retrieval over the approved knowledge base.

Approved `.md` and `.txt` documents are indexed explicitly into PostgreSQL +
pgvector through the storage primitives in ``db.document_loader`` (chunking,
embedding, storage), and retrieved here with a hybrid BM25 + dense ensemble.
The tool returns evidence passages with source metadata; it never generates
answers, and empty or failed retrieval is reported as such so the agent cannot
fabricate business facts.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import rank_bm25
from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.retrievers import BaseRetriever
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings
from pydantic import BaseModel, ConfigDict, Field

from config import OPENROUTER_BASE_URL, DocumentSearchSettings
from db.document_loader import dense_search, load_chunks


if TYPE_CHECKING:
    from langchain_core.callbacks import CallbackManagerForRetrieverRun
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)

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


def resolve_embeddings():
    """Build the configured embedding model for indexing and querying."""
    settings = DocumentSearchSettings()
    model = settings.resolved_embedding_model
    if settings.embedding_provider == "openrouter":
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is not set")
        return OpenAIEmbeddings(
            model=model,
            base_url=OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key,
        )
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    return OpenAIEmbeddings(model=model, api_key=settings.openai_api_key)


def _tokenize(text: str) -> list[str]:
    """Lowercase word tokens; deterministic across platforms and runs."""
    return re.findall(r"\w+", text.lower())


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
    settings: DocumentSearchSettings,
) -> EnsembleRetriever:
    """Combine BM25 and dense retrieval with rank fusion.

    Ensemble weights must be validated against the retrieval evaluation
    dataset before being treated as final.
    """
    bm25_retriever = build_bm25_retriever(chunks, settings.bm25_candidates)
    dense_retriever = DenseRetriever(embeddings=embeddings, candidates=settings.dense_candidates)
    return EnsembleRetriever(
        retrievers=[bm25_retriever, dense_retriever],
        weights=[settings.bm25_weight, 1.0 - settings.bm25_weight],
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
def document_search_tool(query: str, k: int) -> tuple[str, list[DocumentChunkResult]]:
    if not query or not query.strip():
        raise ValueError("query must not be empty")

    try:
        indexed_chunks = load_chunks()
        if not indexed_chunks:
            logger.warning(
                "Document index is empty; run scripts/index_documents.py before querying."
            )
            return "", []

        documents = build_hybrid_retriever(
            indexed_chunks, resolve_embeddings(), DocumentSearchSettings()
        ).invoke(query.strip())

        results = [
            DocumentChunkResult(
                content=document.page_content,
                metadata=DocumentChunkMetadata(
                    source=str(document.metadata["source"]),
                    chunk_index=int(document.metadata["chunk_index"]),
                ),
            )
            for document in documents[:k]
        ]
        evidence_text = "\n\n".join(
            f"<SOURCE>{result.metadata.source}</SOURCE>\n{result.content}" for result in results
        )
    except DocumentSearchError:
        raise
    except Exception as exc:
        logger.error("Document retrieval failed: %s", type(exc).__name__)
        raise DocumentSearchError("Document search is temporarily unavailable.") from exc
    else:
        return evidence_text, results
