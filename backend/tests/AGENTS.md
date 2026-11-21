# tests — PYTEST SUITE

12 test modules over the app, with the whole harness living in `conftest.py` (there is no pytest config section in `pyproject.toml` — default discovery only).

## CAVEATS (verified 2026-10-12)

- **Docker is required and is running in this checkout (verified 2026-10-13).** `docker info` succeeds, so the session fixtures can start the container.
- **The local `.env` leaks into manual settings instantiation.** The suite neutralizes it per test via `_hermetic_settings`, but running `DocumentSearchSettings()` by hand from `backend/` still reads the local `.env` and can shadow the code defaults. Run from a clean worktree or unset the relevant vars when checking defaults by hand.
- `ruff` is configured in `pyproject.toml` but is NOT in the `dev` dependency group (only `pytest` and `testcontainers`), and `.venv/bin/ruff` does not exist — invoke it as `uvx ruff`.
- `test_document_loader.py` is pure — no Docker or testcontainers; it only discovers and chunks under `tmp_path`.
- `test_auth.py` signs tokens with a throwaway RSA key whose public half is served by a stubbed JWKS client, so the real PyJWT path (signature, issuer, `token_use`, `client_id`, expiry) runs offline.
- `conftest` replaces provider embeddings with deterministic fakes, so document search exercises pgvector end to end without provider API calls; tests that monkeypatch `resolve_embeddings` themselves are unaffected.
