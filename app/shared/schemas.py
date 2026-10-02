from typing import Self

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    size: int = Field(20, ge=1, le=100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int

    @classmethod
    def of(cls, items: list[T], total: int, params: PageParams) -> Self:
        return cls(items=items, total=total, page=params.page, size=params.size)


class APIResponse[T](BaseModel):
    success: bool = True
    message: str | None = "success"
    result: T | None = None


def ok[T](data: T, message: str = "success") -> APIResponse[T]:
    return APIResponse(result=data, message=message)