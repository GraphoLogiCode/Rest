import base64
import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.exceptions import PyJWKClientConnectionError

from src.auth import AuthUnavailable, InvalidToken, TokenVerifier
from src.config import Settings
from tests.conftest import ISSUER, SECRET, make_token


@pytest.fixture
def backend() -> str:
    # Token checks do not depend on where data is stored.
    return "memory"


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_private_route_needs_a_token(client: TestClient) -> None:
    response = client.get("/v1/me")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_valid_token_identifies_the_user(client: TestClient) -> None:
    user_id = uuid.uuid4()
    response = client.get("/v1/me", headers=bearer(make_token(user_id)))
    assert response.status_code == 200
    assert response.json()["user_id"] == str(user_id)


@pytest.mark.parametrize(
    "token",
    [
        "not-a-token",
        make_token(exp=int(time.time()) - 3600),
        make_token(exp=None),
        make_token(aud="some-other-api"),
        make_token(aud=None),
        make_token(iss="https://attacker.example/auth/v1"),
        make_token(iss=None),
        make_token(sub="not-a-uuid"),
        make_token(sub=None),
        make_token(role="anon"),
        make_token(role="service_role"),
        make_token(role=None),
        make_token(secret="a-different-secret-of-sufficient-length-x"),
        jwt.encode({"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": ISSUER, "role": "authenticated",
                    "exp": int(time.time()) + 600}, None, algorithm="none"),
    ],
    ids=[
        "garbage", "expired", "no-exp", "wrong-audience", "no-audience", "wrong-issuer", "no-issuer",
        "sub-not-uuid", "no-sub", "anon-key", "service-key", "no-role", "wrong-secret", "alg-none",
    ],
)
def test_bad_tokens_are_rejected(client: TestClient, token: str) -> None:
    response = client.get("/v1/me", headers=bearer(token))
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_token"


def test_every_private_route_rejects_anonymous_requests(client: TestClient) -> None:
    import re
    checked = 0
    for path, operations in client.app.openapi()["paths"].items():
        if not path.startswith("/v1") or path.startswith("/v1/products"):
            continue
        url = re.sub(r"\{[^}]+\}", lambda m: "service" if m.group(0) == "{consent_type}" else str(uuid.uuid4()), path)
        for method in operations.keys() & {"get", "post", "put", "patch", "delete"}:
            assert client.request(method.upper(), url).status_code == 401, f"{method} {path}"
            checked += 1
    assert checked >= 25  # Guard against lazy-router introspection silently checking zero routes.



# Asymmetric signing keys


class StaticKeys:
    """A signing key source that always returns one public key."""

    def __init__(self, public_key: object):
        self.public_key = public_key

    def get_signing_key_from_jwt(self, token: str) -> SimpleNamespace:
        return SimpleNamespace(key=self.public_key)


@pytest.fixture
def ec_key() -> ec.EllipticCurvePrivateKey:
    return ec.generate_private_key(ec.SECP256R1())


def test_es256_token_is_checked_against_the_published_key(ec_key: ec.EllipticCurvePrivateKey) -> None:
    verifier = TokenVerifier(issuer=ISSUER, signing_keys=StaticKeys(ec_key.public_key()))
    user_id = uuid.uuid4()
    assert verifier.verify(make_token(user_id, secret=ec_key, algorithm="ES256")).id == user_id

    other_key = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(InvalidToken):
        verifier.verify(make_token(secret=other_key, algorithm="ES256"))


def test_shared_secret_token_is_refused_when_no_secret_is_configured(ec_key: ec.EllipticCurvePrivateKey) -> None:
    verifier = TokenVerifier(issuer=ISSUER, signing_keys=StaticKeys(ec_key.public_key()))
    with pytest.raises(InvalidToken):
        verifier.verify(make_token())


def test_public_key_cannot_be_used_as_a_shared_secret(ec_key: ec.EllipticCurvePrivateKey) -> None:
    """An HS256 token signed with the public key must not pass, even with both modes on."""
    public_pem = ec_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    def b64(data: bytes) -> bytes:
        return base64.urlsafe_b64encode(data).rstrip(b"=")

    claims = {"sub": str(uuid.uuid4()), "aud": "authenticated", "iss": ISSUER, "role": "authenticated",
              "exp": int(time.time()) + 600}
    signing_input = b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()) + b"." + b64(json.dumps(claims).encode())
    forged = signing_input + b"." + b64(hmac.new(public_pem, signing_input, hashlib.sha256).digest())

    verifier = TokenVerifier(issuer=ISSUER, jwt_secret=SECRET, signing_keys=StaticKeys(ec_key.public_key()))
    with pytest.raises(InvalidToken):
        verifier.verify(forged.decode())


def test_unreachable_signing_keys_are_reported_as_unavailable(ec_key: ec.EllipticCurvePrivateKey) -> None:
    class Unreachable:
        def get_signing_key_from_jwt(self, token: str) -> None:
            raise PyJWKClientConnectionError("network down")

    verifier = TokenVerifier(issuer=ISSUER, signing_keys=Unreachable())
    with pytest.raises(AuthUnavailable):
        verifier.verify(make_token(secret=ec_key, algorithm="ES256"))


def test_verifier_needs_a_way_to_check_tokens() -> None:
    with pytest.raises(ValueError):
        TokenVerifier(issuer=ISSUER)


def test_settings_refuse_to_load_without_the_project_url() -> None:
    with pytest.raises(RuntimeError):
        Settings.from_env({})
    settings = Settings.from_env({"SUPABASE_URL": "https://project.supabase.co/", "CORS_ORIGINS": "http://a, http://b"})
    assert settings.issuer == ISSUER
    assert settings.cors_origins == ("http://a", "http://b")
    assert settings.supabase_jwt_secret is None
