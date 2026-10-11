from typing import Annotated

from fastapi import Depends, Request

from src.storage.base import CheckInExists, Store
from src.storage.memory import MemoryStore

__all__ = ["CheckInExists", "MemoryStore", "Store", "StoreDep", "get_store"]


def get_store(request: Request) -> Store:
    return request.app.state.store


StoreDep = Annotated[Store, Depends(get_store)]
