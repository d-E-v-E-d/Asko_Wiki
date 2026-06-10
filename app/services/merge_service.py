# app/services/merge_service.py
from __future__ import annotations
from pathlib import Path
from typing import Union

from app.config import config
from app.services.log_service import append_log

DOCS_DIR   = Path(config.get("paths", "docs"))
DRAFTS_DIR = Path(config.get("paths", "docs_draft"))
REVIEW_DIR = Path("review"); REVIEW_DIR.mkdir(parents=True, exist_ok=True)

def _safe_rel_md(path: str) -> Path:
    p = (path or "").strip().replace("\\", "/")
    if not p.lower().endswith(".md"):
        p += ".md"
    rel = Path(p)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("Ungültiger Dateipfad")
    return rel

def approve(file: str, user: Union[dict, str]) -> None:
    """
    Draft -> Live (bytegenau), Draft löschen, Logeintrag 'approved'.
    'user' kann CurrentUser-Dict (mit 'name'/'username') oder ein String sein.
    """
    rel = _safe_rel_md(file)
    src = DRAFTS_DIR / rel
    dst = DOCS_DIR / rel
    if not src.exists():
        raise FileNotFoundError("Draft nicht gefunden")

    # Bytegenaue Kopie (verhindert CR/LF-Konvertierung)
    data = src.read_bytes()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data)

    try:
        src.unlink()
    except Exception:
        pass

    append_log(rel.as_posix(), user, "approved")

def reject(file: str, user: Union[dict, str]) -> None:
    """
    Draft verwerfen, Logeintrag 'rejected'.
    """
    rel = _safe_rel_md(file)
    draft_p = DRAFTS_DIR / rel
    if draft_p.exists():
        try:
            draft_p.unlink()
        except Exception as e:
            raise RuntimeError(f"Draft konnte nicht gelöscht werden: {e}")

    append_log(rel.as_posix(), user, "rejected")
