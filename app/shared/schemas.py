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


class APIResponse[T](BaseModel):
    status_code: int
    title: str | None
    message: str | None
    data: T

    @classmethod
    def success(cls, data: T):
        return cls(status_code=200, title=None, message="success", data=data)
