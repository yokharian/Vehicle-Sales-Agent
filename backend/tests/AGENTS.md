# tests — PYTEST SUITE

12 test modules over the app, with the whole harness living in `conftest.py` (there is no pytest config section in `pyproject.toml` — default discovery only).

## CAVEATS (verified 2026-10-12)

- **Docker is required and is running in this checkout (verified 2026-10-13).** `docker info` succeeds, so the session fixtures can start the container.
- **The local `.env` leaks into manual settings instantiation.** The suite neutralizes it per test via `_hermetic_settings`, but running `DocumentSearchSettings()` by hand from `backend/` still reads the local `.env` and can shadow the code defaults. Run from a clean worktree or unset the relevant vars when checking defaults by hand.
- `ruff` is configured in `pyproject.toml` but is NOT in the `dev` dependency group (only `pytest` and `testcontainers`), and `.venv/bin/ruff` does not exist — invoke it as `uvx ruff`.
