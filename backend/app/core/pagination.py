from dataclasses import dataclass

from fastapi import Query
from pydantic import BaseModel


class Page[T](BaseModel):
    """List envelope used by every list endpoint."""

    items: list[T]
    total: int


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def pagination(
    limit: int = Query(20, ge=1, le=100, description="Page size (max 100)."),
    offset: int = Query(0, ge=0, description="Items to skip."),
) -> Pagination:
    return Pagination(limit=limit, offset=offset)
