# version_models.py
from pydantic import BaseModel


class VersionInfo(BaseModel):
    current_version: str
    build_date: str