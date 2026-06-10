# app/services/drafts_service.py
from __future__ import annotations
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import json, uuid
from app.services.log_service import append_log
from app.config import config
from app.site_registry import SITE_KEY_SET, normalize_site, site_folder

# Verzeichnisse
SITES_ROOT = Path(config.get("paths", "sites_root", fallback="sites")).resolve()
SITES_ROOT.mkdir(parents=True, exist_ok=True)
LOG_FILE   = Path('review/changes_log.json').resolve()

DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def _ts() -> str:
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')

ALLOWED_SITES = SITE_KEY_SET

def _norm_site(site: str | None) -> str:
    try:
        s = normalize_site(site)
    except KeyError:
        s = ""
    if s not in ALLOWED_SITES:
        raise ValueError("Invalid site")
    return s

def _docs_dirs(site: str) -> tuple[Path, Path]:
    base = SITES_ROOT / site_folder(site)
    return (base / "docs", base / "docs_draft")

def _safe_rel_md(path: str) -> Path:
    """Nur relative .md-Pfade unterhalb des Draft-Verzeichnisses zulassen."""
    p = (path or '').strip().replace('\\', '/')
    if not p.lower().endswith('.md'):
        p += '.md'
    rel = Path(p)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Ungültiger Dateipfad (nur relative .md erlaubt)')
    return rel

def load_draft(site: str, file: str) -> str:
    site = _norm_site(site)
    rel = _safe_rel_md(file)
    docs_dir, drafts_dir = _docs_dirs(site)

    draft_path = drafts_dir / rel
    if draft_path.exists():
        return draft_path.read_bytes().decode("utf-8", errors="ignore")

    live_path = docs_dir / rel
    if live_path.exists():
        return live_path.read_bytes().decode("utf-8", errors="ignore")

    return ""

def save_draft(site: str, file_rel: str, content: str, user: dict, comment: str | None = None):
    site = _norm_site(site)
    draft_id = str(uuid.uuid4())

    docs_dir, drafts_dir = _docs_dirs(site)
    target = drafts_dir / _safe_rel_md(file_rel)
    target.parent.mkdir(parents=True, exist_ok=True)

    target.write_text(content, encoding="utf-8")

    append_log(file_rel, user, "draft_saved", {"comment": comment, "draft_id": draft_id, "site": site})
    return draft_id


def list_open_drafts(site: str) -> List[str]:
    site = _norm_site(site)
    _, drafts_dir = _docs_dirs(site)
    if not drafts_dir.exists():
        return []
    return [p.relative_to(drafts_dir).as_posix() for p in drafts_dir.rglob("*") if p.is_file() and p.suffix.lower()==".md"]


