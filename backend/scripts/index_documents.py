#!/usr/bin/env python3
"""Knowledge Base Indexing Script.

Indexes approved .md/.txt documents into PostgreSQL + pgvector
(Parse -> Chunk -> Embed -> per-source upsert). Re-run after any change to
the knowledge base or the embedding model. Documents whose model-qualified
chunk hashes match the stored ones are skipped unless --force is given; in
directory mode, sources removed from the knowledge base are purged.
"""

import argparse
import logging
import sys
from pathlib import Path


# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from config import DocumentSearchSettings
from db.document_loader import (
    DocumentLoader,
    content_hash,
    ensure_tables,
    purge_removed_sources,
    stored_chunk_hashes,
    upsert_document_chunks,
)
from tools.document_search import resolve_embeddings


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index knowledge-base documents into pgvector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Operator constraint: single writer per source. Do not run two\n"
            "ingests of the same file simultaneously."
        ),
    )
    parser.add_argument(
        "--documents-dir",
        default="data/documents",
        help="Directory containing approved .md/.txt documents",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Index a single document path instead of every document in --documents-dir",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-embed and rewrite even when the stored content hashes match",
    )
    args = parser.parse_args()

    try:
        ensure_tables()
        loader = DocumentLoader(args.documents_dir)

        if args.file is not None:
            single = Path(args.file)
            documents = [single] if single.is_file() else []
        else:
            documents = loader.discover()

        if not documents:
            if args.file is None:
                # Dir mode: purge before the early return so an emptied
                # knowledge base also clears the index.
                purge_removed_sources(set())
            logger.warning(
                "No supported documents found in %s; check the configuration.",
                args.file if args.file is not None else args.documents_dir,
            )
            return 1

        model_id = DocumentSearchSettings().resolved_embedding_model
        embeddings = None
        indexed_chunks = 0
        skipped_files = 0
        seen_chunks = 0
        for path in documents:
            chunks = loader.chunk(path)
            seen_chunks += len(chunks)
            source = path.name
            desired = [
                (chunk.metadata["chunk_index"], content_hash(model_id, chunk.page_content))
                for chunk in chunks
            ]
            if not args.force and desired == stored_chunk_hashes(source):
                logger.info("Document %s unchanged, skipped (%d chunks).", source, len(chunks))
                skipped_files += 1
                continue
            if embeddings is None:
                embeddings = resolve_embeddings()
            indexed_chunks += upsert_document_chunks(source, chunks, embeddings)

        if args.file is None:
            purge_removed_sources({path.name for path in documents})

        if seen_chunks == 0:
            logger.warning("Documents found but no chunks were produced; check the documents.")
            return 1

        logger.info(
            "Indexed %d chunks from %d documents into PostgreSQL/pgvector (%d unchanged, skipped).",
            indexed_chunks,
            len(documents),
            skipped_files,
        )
    except Exception as exc:
        logger.error("Indexing failed: %s", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
