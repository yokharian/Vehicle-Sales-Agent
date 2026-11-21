# src/db — DATA LAYER

Two stores behind one package: the SQLModel vehicle catalog (relational) and the pgvector document index. `database.py` holds both engines as module globals; every DAO/loader call resolves them at call time.

## HOTSPOTS

- `vehicle_dao.fuzzy_match_make` / `fuzzy_match_model` grade candidates in SQLAlchemy `case`/`func.levenshtein` expressions: containment scores 90, otherwise the normalized Levenshtein percentage; the best candidate at or above `FUZZY_MATCH_THRESHOLD` wins, alphabetically on ties, and empty or >255-byte inputs return `None`.
- `vehicle_dao.search_vehicles` accepts `features` but ignores it: feature filtering is the `_filter_by_features` post-filter in `tools/catalog_search.py`, so callers must not expect the DAO to narrow rows by feature.
- `document_loader` is split by role: `DocumentLoader` only discovers and chunks, all persistence lives in the module-level functions.
- `purge_removed_sources(set())` deletes every stored chunk: an empty active-source set means "purge all", not "purge nothing".
- `DocumentChunk.embedding` is a dim-free `Vector()`, so one index holds one embedding space — changing the embedding model requires a full reindex.
