from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.deps import CurrentUser, _extract_token
from app.config import config
from app.runtime_paths import get_sites_root
from app.security import decode_token
from app.site_registry import SITE_KEYS, normalize_site, site_folder

router = APIRouter(prefix="/sync", tags=["sync"])

SITES_ROOT = get_sites_root()
ALLOWED_SITES = SITE_KEYS


def _is_enabled() -> bool:
    raw = config.get("sync_api", "enabled", os.environ.get("SYNC_API_ENABLED", "0"))
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _sync_token() -> str:
    return str(
        config.get("sync_api", "token", "")
        or os.environ.get("SYNC_API_TOKEN", "")
    ).strip()


def _site_root(site: str) -> Path:
    try:
        site = normalize_site(site)
    except KeyError:
        site = ""
    if site not in ALLOWED_SITES:
        raise HTTPException(status_code=400, detail="Ungueltige site")
    return SITES_ROOT / site_folder(site)


def _safe_rel_md(file: str) -> Path:
    p = (file or "").strip().replace("\\", "/")
    if not p.lower().endswith(".md"):
        p += ".md"
    rel = Path(p)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Ungueltiger Dateipfad")
    return rel


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _entry(site: str, source: str, root: Path, path: Path) -> dict:
    stat = path.stat()
    rel = path.relative_to(root).as_posix()
    return {
        "site": site,
        "source": source,
        "path": rel,
        "repo_path": f"sites/{site_folder(site)}/{root.name}/{rel}",
        "size": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": _sha256(path),
        "content_url": f"/sync/file?site={site}&file={rel}&source={source}",
        "raw_url": f"/{root.name}/{site}/{rel}",
    }


def _auth_sync_token(request: Request) -> bool:
    expected = _sync_token()
    if not expected:
        return False

    header_token = (request.headers.get("X-Sync-Token") or "").strip()
    if header_token and header_token == expected:
        return True

    auth = (request.headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        bearer = auth.split(" ", 1)[1].strip()
        if bearer == expected:
            return True

    return False


def _auth_user(request: Request) -> CurrentUser | None:
    token = _extract_token(request)
    if not token:
        return None
    try:
        data = decode_token(token)
    except Exception:
        return None
    role = str(data.get("role") or "")
    if role not in {"editor", "admin"}:
        return None
    return {
        "username": data.get("sub"),
        "role": role,
        "name": data.get("name") or data.get("sub"),
    }


def require_sync_access(request: Request) -> CurrentUser | dict:
    if not _is_enabled():
        raise HTTPException(status_code=404, detail="Sync API deaktiviert")
    user = _auth_user(request)
    if user:
        return user
    if _auth_sync_token(request):
        return {"username": "sync-api", "role": "admin", "name": "sync-api"}
    raise HTTPException(status_code=401, detail="Not authenticated")


def _collect_site_entries(site: str, scope: Literal["live", "draft", "effective", "all"]) -> list[dict]:
    root = _site_root(site)
    docs_root = root / "docs"
    draft_root = root / "docs_draft"

    live_map = {
        p.relative_to(docs_root).as_posix(): _entry(site, "live", docs_root, p)
        for p in docs_root.rglob("*.md")
    } if docs_root.exists() else {}

    draft_map = {
        p.relative_to(draft_root).as_posix(): _entry(site, "draft", draft_root, p)
        for p in draft_root.rglob("*.md")
    } if draft_root.exists() else {}

    if scope == "live":
        return [live_map[k] for k in sorted(live_map)]
    if scope == "draft":
        return [draft_map[k] for k in sorted(draft_map)]
    if scope == "all":
        out = [live_map[k] for k in sorted(live_map)]
        out.extend(draft_map[k] for k in sorted(draft_map))
        return out

    merged = dict(live_map)
    merged.update(draft_map)
    return [merged[k] for k in sorted(merged)]


@router.get("/ping")
def sync_ping(_auth=Depends(require_sync_access)):
    token_set = bool(_sync_token())
    return {"ok": True, "token_configured": token_set, "sites": list(ALLOWED_SITES)}


@router.get("/list")
def sync_list(
    site: str = Query("all", description="all oder einzelner Bereich"),
    scope: Literal["live", "draft", "effective", "all"] = Query("effective"),
    _auth=Depends(require_sync_access),
):
    selected_sites = list(ALLOWED_SITES) if (site or "").strip().lower() == "all" else [(site or "").strip().lower()]
    for selected_site in selected_sites:
        if selected_site not in ALLOWED_SITES:
            raise HTTPException(status_code=400, detail=f"Ungueltige site: {selected_site}")

    files: list[dict] = []
    for selected_site in selected_sites:
        files.extend(_collect_site_entries(selected_site, scope))

    return {
        "ok": True,
        "site": site,
        "scope": scope,
        "count": len(files),
        "files": files,
    }


@router.get("/file")
def sync_file(
    site: str = Query(...),
    file: str = Query(..., description="Relativer Pfad innerhalb docs/docs_draft"),
    source: Literal["live", "draft", "effective"] = Query("effective"),
    _auth=Depends(require_sync_access),
):
    root = _site_root(site)
    rel = _safe_rel_md(file)
    docs_path = root / "docs" / rel
    draft_path = root / "docs_draft" / rel

    if source == "draft":
        target = draft_path
        resolved_source = "draft"
    elif source == "live":
        target = docs_path
        resolved_source = "live"
    else:
        if draft_path.exists():
            target = draft_path
            resolved_source = "draft"
        else:
            target = docs_path
            resolved_source = "live"

    if not target.exists():
        raise HTTPException(status_code=404, detail="Datei nicht gefunden")

    stat = target.stat()
    return {
        "ok": True,
        "site": site,
        "path": rel.as_posix(),
        "source": resolved_source,
        "repo_path": f"sites/{site_folder(site)}/{target.parent.parent.name}/{rel.as_posix()}",
        "size": stat.st_size,
        "modified_utc": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": _sha256(target),
        "content": _read_text(target),
    }
