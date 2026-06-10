# app/services/log_service.py
from __future__ import annotations
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timezone
import json, os, tempfile, threading

# ----------------- Pfade & Lock -----------------
CHANGELOG = Path("review/changes_log.json")
CHANGELOG.parent.mkdir(parents=True, exist_ok=True)
_lock = threading.Lock()

# ----------------- Konstanten für Actions -----------------
ACTION_DRAFT_SAVED = "draft_saved"
ACTION_APPROVED    = "approved"
ACTION_REJECTED    = "rejected"
ACTION_BUILD_START = "build_started"
ACTION_BUILD_DONE  = "build_finished"
ACTION_VERSION_SET = "version_set"
ACTION_PDF_EXPORTED= "pdf_exported"

# ----------------- Rotation (optional) -----------------
MAX_BYTES = 5 * 1024 * 1024  # 5 MB

def _rotate_if_needed() -> None:
    if CHANGELOG.exists() and CHANGELOG.stat().st_size > MAX_BYTES:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        rot = CHANGELOG.with_name(f"changes_log_{ts}.json")
        CHANGELOG.replace(rot)  # Rename/Move

# ----------------- Helpers -----------------
def _now() -> str:
    # UTC ISO-8601 – stabil für Mehrsystem-Logs
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _display_name(user: Union[dict, str, None]) -> str:
    if isinstance(user, dict):
        return user.get("name") or user.get("username") or str(user)
    return str(user or "unbekannt")

# ----------------- API -----------------
def read_log() -> List[Dict[str, Any]]:
    try:
        return json.loads(CHANGELOG.read_text(encoding="utf-8") or "[]") if CHANGELOG.exists() else []
    except Exception:
        return []

def query_log(
    *,
    action: Optional[str] = None,
    file: Optional[str] = None,
    user: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    """
    Filtert Logeinträge. limit [1..1000]
    """
    rows = read_log()
    if action:
        rows = [r for r in rows if r.get("action") == action]
    if file:
        rows = [r for r in rows if r.get("file") == file]
    if user:
        rows = [r for r in rows if r.get("user") == user]
    rows.sort(key=lambda r: r.get("timestamp", ""), reverse=True)
    limit = max(1, min(limit, 1000))
    return rows[:limit]

def append_log(
    file: Optional[str],
    user: Union[dict, str, None],
    action: str,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Einheitlicher Logeintrag. Beispiel:
    {
      "file": "Schadenbearbeitung_Generell/zweck.md",
      "user": "Max Mustermann",
      "action": "draft_saved",
      "timestamp": "2025-11-11T09:34:21+00:00",
      "details": {"comment": "..."}  # optional
    }
    """
    if not isinstance(action, str) or not action:
        return  # defensiv: keine invalide Action schreiben

    entry: Dict[str, Any] = {
        "file": file or "",
        "user": _display_name(user),
        "action": action,
        "timestamp": _now(),
    }
    if details:
        entry["details"] = details

    with _lock:
        _rotate_if_needed()
        data = read_log()
        data.append(entry)
        # atomar schreiben
        tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8", dir=str(CHANGELOG.parent))
        try:
            json.dump(data, tmp, ensure_ascii=False, indent=2)
            tmp.close()
            os.replace(tmp.name, CHANGELOG)
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
