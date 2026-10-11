from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.auth.tokens import AuthenticatedUser, AuthUnavailable, InvalidToken
from src.errors import ApiError

_bearer = HTTPBearer(auto_error=False)
_CHALLENGE = {"WWW-Authenticate": "Bearer"}


def current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AuthenticatedUser:
    """The signed-in user, taken from the access token and nowhere else."""
    if credentials is None:
        raise ApiError(401, "not_authenticated", "Sign in to continue.", _CHALLENGE)
    try:
        return request.app.state.token_verifier.verify(credentials.credentials)
    except InvalidToken as exc:
        raise ApiError(401, "invalid_token", "Your session is not valid. Sign in again.", _CHALLENGE) from exc
    except AuthUnavailable as exc:
        raise ApiError(503, "auth_unavailable", "Sign-in could not be checked. Try again shortly.") from exc


CurrentUser = Annotated[AuthenticatedUser, Depends(current_user)]
