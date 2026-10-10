# ADR-003: PostgreSQL as the Primary Datastore

**Status:** Accepted

## Context

The agent requires persistent business data for vehicle inventory, conversation-related data, and indexed knowledge. The POC should avoid introducing separate databases when a single datastore can satisfy these requirements.

## Decision

Use PostgreSQL as the primary persistent datastore and source of truth. Use PostgreSQL with pgvector for dense knowledge retrieval, while structured business data remains relational. Application components should access persistence through explicit interfaces rather than depending directly on storage details.

## Alternatives

* SQLite for the POC.
* PostgreSQL plus a separate vector database.
* PostgreSQL plus an external search engine.

## Trade-offs

* Keeps the infrastructure small and familiar.
* pgvector avoids introducing a separate vector database.
* Search capabilities are more limited than a dedicated search system.
* Scaling PostgreSQL for very large retrieval workloads may eventually require a different architecture.

## Revisit when

Revisit if production scale or search requirements exceed what PostgreSQL can provide efficiently.
