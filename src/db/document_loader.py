"""
Loading and chunking of approved knowledge-base documents (``.md`` / ``.txt``).

The :class:`DocumentLoader` class is the single API for loading and chunking
approved knowledge-base documents.
"""

from __future__ import annotations

import logging
from pathlib import Path

from langchain_core.documents import Document
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)


logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = (".md", ".txt")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 100
_MARKDOWN_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]


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

        splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        chunks = [
            Document(page_content=piece, metadata={"source": path.name})
            for section in section_texts
            for piece in splitter.split_text(section)
        ]
        for chunk_index, chunk in enumerate(chunks):
            chunk.metadata["chunk_index"] = chunk_index
        return chunks
