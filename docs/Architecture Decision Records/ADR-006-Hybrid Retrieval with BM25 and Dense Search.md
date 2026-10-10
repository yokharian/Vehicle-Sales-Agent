# ADR-006: Hybrid Retrieval with BM25 and Dense Search

**Status:** Draft

## Context

The knowledge base contains both natural-language business questions and exact terms such as product names, requirements, and numerical values. Dense retrieval handles semantic similarity well, while lexical retrieval can provide stronger matching for exact terminology.

## Decision

Use a hybrid retriever combining BM25 and dense vector retrieval. Dense embeddings are stored in PostgreSQL using pgvector, while BM25 operates over the indexed document chunks. The initial weighting and retrieval parameters are configurable and will be validated against the retrieval evaluation set.

## Alternatives

* Dense retrieval only.
* BM25 retrieval only.
* A dedicated external search engine.

## Trade-offs

* Improves coverage across semantic and exact-match queries.
* Adds retrieval complexity compared with a single retriever.
* Requires evaluating and maintaining two retrieval strategies.
* Does not justify additional search infrastructure at POC scale.

## Revisit when

Revisit if evaluation shows that one retrieval strategy is sufficient or if corpus size and search requirements justify a dedicated search system.
