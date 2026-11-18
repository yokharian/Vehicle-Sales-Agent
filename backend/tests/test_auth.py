"""Tests for the Cognito-backed LangGraph custom auth middleware.

Tokens are signed with a throwaway RSA key whose public half is served by a
stubbed JWKS client, so the full PyJWT verification path (signature, issuer,
token_use, client_id, expiry) runs without network access.
"""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

import auth


ISSUER = auth.cognito.issuer
CLIENT_ID = auth.cognito.app_client_id

_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_OTHER_PRIVATE_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PUBLIC_JWK = jwt.algorithms.RSAAlgorithm.to_jwk(_PRIVATE_KEY.public_key(), as_dict=True)
_PUBLIC_JWK.update({"kid": "test-key", "use": "sig", "alg": "RS256"})


@pytest.fixture(autouse=True)
def _stub_jwks(monkeypatch):
    """Serve the throwaway public key instead of hitting Cognito."""
    signing_key = SimpleNamespace(key=jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(_PUBLIC_JWK)))
    monkeypatch.setattr(auth._jwks_client, "get_signing_key_from_jwt", lambda *_: signing_key)


def make_token(
    sub: str = "user-abc",
    issuer: str = ISSUER,
    client_id: str = CLIENT_ID,
    token_use: str = "access",
    username: str = "testuser",
    expires_at: datetime | None = None,
    key=_PRIVATE_KEY,
) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": sub,
        "iss": issuer,
        "iat": int(now.timestamp()),
        "exp": int((expires_at or now + timedelta(hours=1)).timestamp()),
        "token_use": token_use,
        "client_id": client_id,
        "username": username,
    }
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "test-key"})


def authenticate(authorization: str):
    return asyncio.run(auth.get_current_user(authorization))


class TestValidTokens:
    def test_valid_token_authenticates_sub(self):
        user = authenticate(f"Bearer {make_token()}")

        assert user["identity"] == "user-abc"
        assert user["display_name"] == "testuser"
        assert user["is_authenticated"] is True

    def test_identity_comes_from_sub_not_username(self):
        token = make_token(sub="user-xyz", username="someone-else")

        user = authenticate(f"Bearer {token}")

        assert user["identity"] == "user-xyz"
        assert user["display_name"] == "someone-else"


class TestRejectedTokens:
    def test_missing_bearer_scheme_rejected(self):
        for authorization in ("", "Basic dXNlcjpwYXNz", f"{make_token()}"):
            with pytest.raises(auth.Auth.exceptions.HTTPException) as exc:
                authenticate(authorization)
            assert exc.value.status_code == 401

    def test_expired_token_rejected(self):
        expired = datetime.now(UTC) - timedelta(minutes=5)

        with pytest.raises(auth.Auth.exceptions.HTTPException) as exc:
            authenticate(f"Bearer {make_token(expires_at=expired)}")
        assert exc.value.status_code == 401

    def test_wrong_issuer_rejected(self):
        token = make_token(issuer="https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_EVIL")

        with pytest.raises(auth.Auth.exceptions.HTTPException) as exc:
            authenticate(f"Bearer {token}")
        assert exc.value.status_code == 401

    def test_id_token_rejected(self):
        with pytest.raises(auth.Auth.exceptions.HTTPException) as exc:
            authenticate(f"Bearer {make_token(token_use='id')}")
        assert exc.value.status_code == 401

    def test_wrong_client_id_rejected(self):
        with pytest.raises(auth.Auth.exceptions.HTTPException) as exc:
            authenticate(f"Bearer {make_token(client_id='other-app-client')}")
        assert exc.value.status_code == 401

    def test_token_signed_with_other_key_rejected(self):
        token = make_token(key=_OTHER_PRIVATE_KEY)

        with pytest.raises(auth.Auth.exceptions.HTTPException) as exc:
            authenticate(f"Bearer {token}")
        assert exc.value.status_code == 401


class TestDisabledAuth:
    def test_without_user_pool_requests_pass_anonymously(self, monkeypatch):
        monkeypatch.setattr(auth.cognito, "user_pool_id", None)

        for authorization in ("Bearer whatever", ""):
            user = authenticate(authorization)

            assert user["identity"] == "anonymous"
            assert user["is_authenticated"] is True


def make_auth_context(resource: str, action: str, identity: str):
    user = SimpleNamespace(
        identity=identity,
        is_authenticated=True,
        display_name=identity,
        permissions=[],
    )
    return auth.Auth.types.AuthContext(
        user=user,
        permissions=["authenticated"],
        resource=resource,
        action=action,
    )


def authorize(resource: str, action: str, value: dict, identity: str = "user-abc"):
    ctx = make_auth_context(resource, action, identity)
    return asyncio.run(auth.add_owner(ctx, value))


class TestOwnerAuthorization:
    def test_create_tags_owner_metadata_and_returns_filter(self):
        value = {"metadata": {}}

        filters = authorize("threads", "create", value)

        assert filters == {"owner": "user-abc"}
        assert value["metadata"]["owner"] == "user-abc"

    def test_create_without_metadata_dict_creates_one(self):
        value = {"thread_id": "123"}

        filters = authorize("threads", "create", value)

        assert filters == {"owner": "user-abc"}
        assert value["metadata"]["owner"] == "user-abc"

    def test_read_returns_owner_filter(self):
        value = {"thread_id": "123", "metadata": {"other": "x"}}

        filters = authorize("threads", "read", value)

        assert filters == {"owner": "user-abc"}

    def test_search_returns_owner_filter(self):
        filters = authorize("threads", "search", {})

        assert filters == {"owner": "user-abc"}

    def test_run_create_run_is_scoped_to_owner(self):
        value = {"metadata": {}}

        filters = authorize("runs", "create_run", value)

        assert filters == {"owner": "user-abc"}

    def test_identities_are_isolated(self):
        filters_a = authorize("threads", "search", {}, identity="user-a")
        filters_b = authorize("threads", "search", {}, identity="user-b")

        assert filters_a == {"owner": "user-a"}
        assert filters_b == {"owner": "user-b"}
