from __future__ import annotations

import os
from pathlib import Path


def get_app_root() -> Path:
    env_root = os.getenv("APP_ROOT")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[1]


def get_repo_root() -> Path:
    return get_app_root()


def get_sites_root() -> Path:
    return get_app_root() / "sites"


def get_site_build_root() -> Path:
    return get_app_root() / "site"

