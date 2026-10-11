import uuid
from dataclasses import dataclass
from typing import Any, Protocol

import jwt
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from src.config import Settings

# Algorithms accepted for keys published by the project's JWKS endpoint.
ASYMMETRIC_ALGORITHMS = ("ES256", "RS256")


class InvalidToken(Exception):
    """The token is missing, malformed, expired, or not issued for this API."""


class AuthUnavailable(Exception):
    """The signing keys could not be fetched, so no token can be checked."""


@dataclass(frozen=True)
class AuthenticatedUser:
    id: uuid.UUID


class SigningKeySource(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


class TokenVerifier:
    """Validates a Supabase access token and returns the user it belongs to.

    Asymmetric tokens are checked against the project's published keys. A
    shared-secret token is accepted only when a secret is configured, and only
    with HS256, so a public key can never be passed off as a shared secret.
    """

    def __init__(
        self,
        *,
        issuer: str,
        audience: str = "authenticated",
        jwt_secret: str | None = None,
        signing_keys: SigningKeySource | None = None,
        leeway_seconds: int = 10,
    ):
        if not jwt_secret and signing_keys is None:
            raise ValueError("TokenVerifier needs a JWT secret or a signing key source")
        self._issuer = issuer
        self._audience = audience
        self._secret = jwt_secret
        self._signing_keys = signing_keys
        self._leeway = leeway_seconds

    @classmethod
    def from_settings(cls, settings: Settings) -> "TokenVerifier":
        jwks = PyJWKClient(f"{settings.issuer}/.well-known/jwks.json", cache_keys=True, lifespan=600)
        return cls(
            issuer=settings.issuer,
            audience=settings.jwt_audience,
            jwt_secret=settings.supabase_jwt_secret,
            signing_keys=jwks,
        )

    def verify(self, token: str) -> AuthenticatedUser:
        try:
            algorithm = jwt.get_unverified_header(token).get("alg")
        except jwt.PyJWTError as exc:
            raise InvalidToken("malformed token") from exc

        if algorithm == "HS256" and self._secret:
            key: Any = self._secret
        elif algorithm in ASYMMETRIC_ALGORITHMS and self._signing_keys is not None:
            try:
                key = self._signing_keys.get_signing_key_from_jwt(token).key
            except PyJWKClientConnectionError as exc:
                raise AuthUnavailable("signing keys unavailable") from exc
            except jwt.PyJWTError as exc:
                raise InvalidToken("unknown signing key") from exc
        else:
            raise InvalidToken("unsupported algorithm")

        try:
            claims = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self._audience,
                issuer=self._issuer,
                leeway=self._leeway,
                options={"require": ["exp", "sub", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken("token rejected") from exc

        # The project's anon and service keys are also JWTs; only a signed-in
        # user's token may act on user data.
        if claims.get("role") != "authenticated":
            raise InvalidToken("not a user token")
        try:
            return AuthenticatedUser(id=uuid.UUID(str(claims["sub"])))
        except ValueError as exc:
            raise InvalidToken("subject is not a user id") from exc
