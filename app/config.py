# app/config.py
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]  # .../app/.. -> Projektwurzel
_DEFAULTS = {
    "paths": {
        "docs": "docs",
        "docs_draft": "docs_draft",
        "versions": "versions",
        "pdf_history": "pdf_history",
        "pdf_history_network": r"\\server\Vordrucke\David\Arbeitsanweisung_Asko\pdf_history"
    },
    "security": {
        "cookie_name": "editor_session",
        "jwt_secret": "CHANGE_ME_DEV",
        "jwt_alg": "HS256",
        "token_ttl_minutes": 480
    },
    "auth": {
        "users_file": "app/auth/users.json"
    },
    "sync_api": {
        "enabled": False,
        "token": ""
    },
    "pdf": {
        "engine": "wkhtmltopdf",
        "wkhtmltopdf_path": "C:/tools/wkhtmltopdf/bin/wkhtmltopdf.exe",
        "filename_pattern": "Arbeitsanweisung_v{version}_{date}.pdf"
    }
}

class _Config:
    def __init__(self) -> None:
        # Konfigurationsdatei suchen: ENV > Projektwurzel/config.json
        env_path = os.getenv("APP_CONFIG")
        if env_path:
            candidate = Path(env_path)
        else:
            candidate = _PROJECT_ROOT / "config.json"

        self._data = dict(_DEFAULTS)
        try:
            if candidate.exists():
                loaded = json.loads(candidate.read_text(encoding="utf-8"))
                # flach zusammenführen (2 Ebenen)
                for sect, vals in loaded.items():
                    if isinstance(vals, dict):
                        self._data.setdefault(sect, {})
                        self._data[sect].update(vals)
                    else:
                        self._data[sect] = vals
        except Exception:
            # Bei Fehlern einfach mit Defaults weiter
            pass

    def get(self, section: str, key: str, default: Optional[Any] = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    def section(self, section: str) -> dict:
        return self._data.get(section, {})

    def project_root(self) -> Path:
        return _PROJECT_ROOT

config = _Config()
