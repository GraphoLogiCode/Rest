from typing import Any

from fastapi import Depends

from src.auth import CurrentUser
from src.errors import ApiError
from src.storage import StoreDep


def require_consent(consent_type: str) -> Any:
    """A route dependency that refuses the request unless the user has an active consent."""

    def check(user: CurrentUser, store: StoreDep) -> None:
        if store.active_consent(user.id, consent_type) is None:
            raise ApiError(
                403, "consent_required", f"This needs your '{consent_type}' consent.",
                details={"consent_type": consent_type},
            )

    return Depends(check)
