from pydantic import BaseModel

class ReviewSummary(BaseModel):
    summary: str
    frontend: str | None = None
    backend: str | None = None
    refactor: str | None = None
