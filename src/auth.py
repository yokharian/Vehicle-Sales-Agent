"""LangGraph custom authentication and authorization backed by Amazon Cognito.

The middleware is optional and activated by environment: when both
`COGNITO_REGION` and `COGNITO_USER_POOL_ID` are set, requests must carry a
Cognito access token as `Authorization: Bearer <jwt>` — the signature is
checked against the user pool's JWKS endpoint (RS256, fetched once and
cached by `PyJWKClient`) along with the issuer
(`https://cognito-idp.<region>.amazonaws.com/<user_pool_id>`), the expiry
(30s leeway for clock skew), the `token_use` claim (`access`) and the
`client_id` when `COGNITO_APP_CLIENT_ID` is configured — and resources
(threads, runs) are scoped to the caller so conversations stay private per
user. When the user pool is unset the server runs open: every request
shares one anonymous identity and no AWS infrastructure is needed (the
pgvector container is the only backend). The intended client is
agent-chat-ui's Amplify auth, whose `authFetch` sends the Cognito access
token as the bearer.

Environment (see `config.py` / `.env.example`):
  - COGNITO_REGION + COGNITO_USER_POOL_ID (optional; set both to enable JWT auth)
  - COGNITO_APP_CLIENT_ID (optional; enforce the token's client_id)
"""

import asyncio
import sys
from pathlib import Path

import jwt
from langgraph_sdk import Auth


sys.path.append(str(Path(__file__).parent))

from config import CognitoSettings


auth = Auth()

cognito = CognitoSettings()

HTTPException = Auth.exceptions.HTTPException

ANONYMOUS_IDENTITY = "anonymous"

_jwks_client: jwt.PyJWKClient | None = (
    jwt.PyJWKClient(cognito.jwks_uri) if cognito.enabled else None
)


def _decode_token(token: str) -> dict:
    """Verify the token against the user pool's JWKS.

    Synchronous on purpose: PyJWKClient fetches the JWKS over HTTP with
    urllib, which would block the event loop (LangGraph dev aborts on it via
    blockbuster) — callers run this in a worker thread.
    """
    client = _jwks_client
    if client is None:
        raise HTTPException(401, "Auth is not configured (Cognito user pool is unset)")
    signing_key = client.get_signing_key_from_jwt(token)
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        issuer=cognito.issuer,
        options={"require": ["exp", "sub"]},
        leeway=30,
    )
    if payload.get("token_use") != "access":
        raise jwt.InvalidTokenError("Expected a Cognito access token")
    if cognito.app_client_id and payload.get("client_id") != cognito.app_client_id:
        raise jwt.InvalidTokenError("Token was issued to a different app client")
    return payload


@auth.authenticate
async def get_current_user(authorization: str) -> Auth.types.MinimalUserDict:
    """Validate the Bearer token, or return an anonymous user when auth is off."""
    if not cognito.enabled:
        return {"identity": ANONYMOUS_IDENTITY, "is_authenticated": True}

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Expected Authorization scheme: Bearer <access_token>")

    try:
        payload = await asyncio.to_thread(
            _decode_token, authorization.removeprefix("Bearer ").strip()
        )
    except (jwt.PyJWTError, jwt.PyJWKClientError) as e:
        raise HTTPException(401, f"Invalid token: {e}") from None

    return {
        "identity": payload["sub"],
        "display_name": payload.get("username"),
        "is_authenticated": True,
    }


async def add_owner(
    ctx: Auth.types.AuthContext,
    value: dict,
) -> dict:
    """Scope every resource to its creator.

    On thread creation the owner is written into the thread's metadata; on
    every other event the returned filter restricts access to that owner.
    """
    if ctx.resource == "threads" and ctx.action == "create":
        metadata = value.setdefault("metadata", {})
        metadata["owner"] = ctx.user.identity
    return {"owner": ctx.user.identity}


auth.on.threads.create(add_owner)
auth.on.threads.create_run(add_owner)
auth.on.threads.read(add_owner)
auth.on.threads.search(add_owner)
auth.on.threads.update(add_owner)
auth.on.threads.delete(add_owner)
