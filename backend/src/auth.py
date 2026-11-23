import asyncio
import logging
import sys
from pathlib import Path

import jwt
from langgraph_sdk import Auth


sys.path.append(str(Path(__file__).parent))

from config import CognitoSettings


logger = logging.getLogger(__name__)

auth = Auth()

cognito = CognitoSettings()

HTTPException = Auth.exceptions.HTTPException

ANONYMOUS_IDENTITY = "anonymous"

_jwks_client: jwt.PyJWKClient | None = (
    jwt.PyJWKClient(cognito.jwks_uri) if cognito.enabled else None
)


def _decode_token(token: str) -> dict:
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
    expected_client_ids = cognito.expected_app_client_ids
    if expected_client_ids and payload.get("client_id") not in expected_client_ids:
        raise jwt.InvalidTokenError("Token was issued to a different app client")
    return payload


@auth.authenticate
async def get_current_user(authorization: str) -> Auth.types.MinimalUserDict:
    if not cognito.enabled:
        return {"identity": ANONYMOUS_IDENTITY, "is_authenticated": True}

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Expected Authorization scheme: Bearer <access_token>")

    try:
        payload = await asyncio.to_thread(
            _decode_token, authorization.removeprefix("Bearer ").strip()
        )
    except jwt.PyJWKClientConnectionError:
        logger.exception("Cognito JWKS unreachable at %s", cognito.jwks_uri)
        raise HTTPException(
            503,
            "Cognito JWKS is unreachable; verify COGNITO_REGION and COGNITO_USER_POOL_ID",
        ) from None
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
