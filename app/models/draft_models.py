# draft_models.py
from pydantic import BaseModel
from typing import Optional


class DraftMeta(BaseModel):
    id: str
    file: str
    user: str
    timestamp: str
    comment: Optional[str] = None


class DraftContent(BaseModel):
    markdown: str


