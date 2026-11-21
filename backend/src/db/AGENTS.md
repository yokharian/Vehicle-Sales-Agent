# src/db — DATA LAYER

Two stores behind one package: the SQLModel vehicle catalog (relational) and the pgvector document index. `database.py` holds both engines as module globals; every DAO/loader call resolves them at call time.

## HOTSPOTS

- `vehicle_dao.fuzzy_match_make` / `fuzzy_match_model` express scoring as SQLAlchemy `case`/`func.levenshtein` expressions; read the docstring before editing.
- `vehicle_dao.search_vehicles` accepts `features` but ignores it: feature filtering is the `_filter_by_features` post-filter in `tools/catalog_search.py`, so callers must not expect the DAO to narrow rows by feature.
- `document_loader` is split by role: `DocumentLoader` only discovers and chunks, all persistence lives in the module-level functions.
