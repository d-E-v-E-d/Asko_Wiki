# log_models.py
from pydantic import BaseModel


class ChangeLogEntry(BaseModel):
    file: str
    user: str
    action: str
    timestamp: str
    details: dict | None = None


