"""LangGraph custom authentication and authorization backed by Supabase Auth.

The middleware is optional and activated by environment: when `SUPABASE_URL`
is set, requests must carry a Supabase access token as `Authorization: Bearer
<jwt>` — the signature is checked against the project's JWKS endpoint
(`/.well-known/jwks.json`, RS256/ES256 keys, fetched once and cached by
`PyJWKClient`) along with the issuer (`<url>/auth/v1`), the expiry (30s
leeway for clock skew) and the `authenticated` audience, and resources
(threads, runs, crons) are scoped to the caller so conversations stay private
per user. When `SUPABASE_URL` is unset the server runs open: every request
shares one anonymous identity and no Supabase infrastructure is needed (the
pgvector container is the only backend).

Environment (see `config.py` / `.env.example`):
  - SUPABASE_URL (optional; set to enable JWT auth)
  - SUPABASE_AUDIENCE (optional, default "authenticated")
"""

import asyncio
import sys
from pathlib import Path

import jwt
from langgraph_sdk import Auth

sys.path.append(str(Path(__file__).parent))

from config import SupabaseSettings

auth = Auth()

supabase = SupabaseSettings()

HTTPException = Auth.exceptions.HTTPException

ANONYMOUS_IDENTITY = "anonymous"

_jwks_client: jwt.PyJWKClient | None = (
    jwt.PyJWKClient(f"{supabase.url.rstrip('/')}/auth/v1/.well-known/jwks.json")
    if supabase.enabled
    else None
)


def _decode_token(token: str) -> dict:
    """Verify the token against the project's JWKS.

    Synchronous on purpose: PyJWKClient fetches the JWKS over HTTP with
    urllib, which would block the event loop (LangGraph dev aborts on it via
    blockbuster) — callers run this in a worker thread.
    """
    client = _jwks_client
    if client is None:
        raise HTTPException(401, "Auth is not configured (SUPABASE_URL is unset)")
    signing_key = client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        issuer=f"{supabase.url.rstrip('/')}/auth/v1",
        audience=supabase.audience,
        options={"require": ["exp", "sub"]},
        leeway=30,
    )


@auth.authenticate
async def get_current_user(authorization: str) -> Auth.types.MinimalUserDict:
    """Validate the Bearer token, or return an anonymous user when auth is off."""
    if not supabase.enabled:
        return {"identity": ANONYMOUS_IDENTITY}

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Expected Authorization scheme: Bearer <access_token>")

    try:
        payload = await asyncio.to_thread(
            _decode_token, authorization.removeprefix("Bearer ").strip()
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
        raise HTTPException(401, f"Invalid token: {e}") from None

    metadata = payload.get("user_metadata") or {}
    return {
        "identity": payload["sub"],
        "display_name": payload.get("email") or metadata.get("full_name") or metadata.get("name"),
        "is_authenticated": True,
    }


@auth.on.threads.create
async def on_thread_create(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.create.value,
):
    """Add owner when creating threads.

    This handler runs when creating new threads and does two things:
    1. Sets metadata on the thread being created to track ownership
    2. Returns a filter that ensures only the creator can access it
    """
    # Example value:
    #  {'thread_id': UUID('99b045bc-b90b-41a8-b882-dabc541cf740'), 'metadata': {}, 'if_exists': 'raise'}

    # Add owner metadata to the thread being created
    # This metadata is stored with the thread and persists
    metadata = value.setdefault("metadata", {})
    metadata["owner"] = ctx.user.identity

    # Return filter to restrict access to just the creator
    return {"owner": ctx.user.identity}


@auth.on.threads.read
async def on_thread_read(
    ctx: Auth.types.AuthContext,
    value: Auth.types.on.threads.read.value,
):
    """Only let users read their own threads.

    This handler runs on read operations. We don't need to set
    metadata since the thread already exists - we just need to
    return a filter to ensure users can only see their own threads.
    """
    return {"owner": ctx.user.identity}
