# src/tools — LANGCHAIN TOOLS

Three `@tool` functions the agent can call, each with pydantic input/output schemas. Their argument schemas ARE the model's interface (ADR-002), so field names, descriptions and constraints are contract — not documentation.

## HOTSPOTS

- `catalog_search_tool` (~100 lines) does validation, fuzzy resolution, DB read, feature post-filter, sorting and dual serialization in one body.
- `document_search_tool` reloads chunks and rebuilds the BM25 index per query — the retrieval hotspot.
- `DenseRetriever._get_relevant_documents` carries `# noqa: ARG002` on `run_manager` for interface compatibility; keep the signature.
