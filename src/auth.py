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
    if supabase.url is not None
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
        return {"identity": ANONYMOUS_IDENTITY, "is_authenticated": True}

    if not authorization.startswith("Bearer "):
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


@auth.on
async def add_owner(ctx: Auth.types.AuthContext, value: dict) -> Auth.types.FilterType:
    """Scope resources to their creator: private threads per user.

    Tags created resources with the caller's identity in metadata; every
    action gets a metadata filter so users only see resources they own.
    With auth disabled, every request shares the anonymous identity.
    """
    filters = {"owner": ctx.user.identity}
    value.setdefault("metadata", {}).update(filters)
    return filters
