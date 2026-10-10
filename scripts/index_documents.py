#!/usr/bin/env python3
"""Knowledge Base Indexing Script.

Indexes approved .md/.txt documents into PostgreSQL + pgvector
(Parse -> Chunk -> Embed -> Full replace). Re-run after any change to the
knowledge base or the embedding model.
"""

import argparse
import logging
import sys
from pathlib import Path


# Add src to path for imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from tools.document_search import (
    chunk_documents,
    discover_documents,
    reindex,
    resolve_embeddings,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Index knowledge-base documents into pgvector.")
    parser.add_argument(
        "--documents-dir",
        default="data/documents",
        help="Directory containing approved .md/.txt documents",
    )
    args = parser.parse_args()

    try:
        documents = discover_documents(args.documents_dir)
        if not documents:
            logger.warning(
                "No supported documents found in %s; check the configuration.", args.documents_dir
            )
            return 1

        chunks = chunk_documents(documents)
        if not chunks:
            logger.warning("Documents found but no chunks were produced; check the documents.")
            return 1

        embeddings = resolve_embeddings()
        indexed = reindex(chunks, embeddings)
        logger.info(
            "Indexed %d chunks from %d documents into PostgreSQL/pgvector.",
            indexed,
            len(documents),
        )
    except Exception as exc:
        logger.error("Indexing failed: %s", type(exc).__name__)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
