from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

class RoutineItem(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Annotated[str, StringConstraints(pattern=r'^(?:[a-f0-9]{32}|[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})$')]
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    period: Literal['morning', 'evening']
    completedOn: date | None = None
    product_id: Annotated[str, StringConstraints(max_length=100)] | None = None

class RoutineDocument(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: Annotated[int, Field(strict=True, ge=0)]
    items: Annotated[list[RoutineItem], Field(max_length=100)]
