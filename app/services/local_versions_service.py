from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import json
import os
import posixpath
import shutil

from fastapi import HTTPException

from app.config import config
from app.runtime_paths import get_app_root
from app.site_registry import normalize_site, site_folder


def _configured_versions_root() -> Path:
    raw = str(config.get("paths", "versions", "") or "").strip()
    app_root = get_app_root()
    if not raw:
        return app_root / "versions"
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/srv/arbeitsanweisung/app/"):
        suffix = normalized[len("/srv/arbeitsanweisung/app/"):].strip("/")
        return app_root / (suffix or "versions")
    if os.name == "nt" and normalized == "/srv/arbeitsanweisung/versions":
        return app_root / "versions"
    return Path(raw)


VERSIONS_ROOT = _configured_versions_root()


def _safe_rel_md(file: str | Path) -> Path:
    value = str(file or "").strip().replace("\\", "/").strip("/")
    if not value:
        raise HTTPException(status_code=400, detail="Datei fehlt")
    if not value.lower().endswith(".md"):
        value += ".md"
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Ungueltiger Dateipfad")
    return rel


def _site_root(repo_root: Path, area: str) -> Path:
    return repo_root / "sites" / site_folder(normalize_site(area))


def _version_dir(area: str, rel: Path) -> Path:
    rel_posix = rel.as_posix()
    stem = rel_posix[:-3] if rel_posix.lower().endswith(".md") else rel_posix
    return VERSIONS_ROOT / normalize_site(area) / Path(stem)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_local_version(
    repo_root: Path,
    area: str,
    file: str | Path,
    *,
    user: str | dict[str, Any] | None = None,
    action: str = "approved",
    note: str = "",
) -> dict[str, Any] | None:
    site = normalize_site(area)
    rel = _safe_rel_md(file)
    live_file = _site_root(repo_root, site) / "docs" / rel
    if not live_file.exists() or not live_file.is_file():
        return None

    version_dir = _version_dir(site, rel)
    version_dir.mkdir(parents=True, exist_ok=True)

    ts = _timestamp()
    target = version_dir / f"{ts}.md"
    counter = 1
    while target.exists():
        target = version_dir / f"{ts}-{counter}.md"
        counter += 1

    shutil.copy2(live_file, target)
    user_name = user.get("name") or user.get("username") if isinstance(user, dict) else str(user or "")
    meta = {
        "area": site,
        "file": rel.as_posix(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version_id": target.stem,
        "action": action,
        "user": user_name or "unbekannt",
        "note": note,
        "source": live_file.relative_to(repo_root).as_posix(),
    }
    meta_path = target.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**meta, "path": target.as_posix()}


def list_local_versions(area: str, file: str | Path, limit: int = 50) -> list[dict[str, Any]]:
    site = normalize_site(area)
    rel = _safe_rel_md(file)
    version_dir = _version_dir(site, rel)
    if not version_dir.exists():
        return []

    items: list[dict[str, Any]] = []
    for md_path in sorted(version_dir.glob("*.md"), key=lambda p: p.name, reverse=True):
        meta_path = md_path.with_suffix(".json")
        meta: dict[str, Any] = {}
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        stat = md_path.stat()
        items.append({
            "version_id": md_path.stem,
            "area": site,
            "file": rel.as_posix(),
            "timestamp": meta.get("timestamp") or datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
            "user": meta.get("user") or "unbekannt",
            "action": meta.get("action") or "approved",
            "note": meta.get("note") or "",
            "size": stat.st_size,
        })
        if len(items) >= limit:
            break
    return items


def read_local_version(area: str, file: str | Path, version_id: str) -> str:
    site = normalize_site(area)
    rel = _safe_rel_md(file)
    clean_id = Path(str(version_id or "").strip()).name
    if not clean_id:
        raise HTTPException(status_code=400, detail="Version fehlt")
    version_path = _version_dir(site, rel) / f"{clean_id}.md"
    if not version_path.exists() or not version_path.is_file():
        raise HTTPException(status_code=404, detail="Version nicht gefunden")
    return version_path.read_text(encoding="utf-8", errors="ignore")


def rollback_to_local_version(
    repo_root: Path,
    area: str,
    file: str | Path,
    version_id: str,
    *,
    user: str | dict[str, Any] | None = None,
) -> dict[str, Any]:
    site = normalize_site(area)
    rel = _safe_rel_md(file)
    live_file = _site_root(repo_root, site) / "docs" / rel

    if live_file.exists():
        create_local_version(repo_root, site, rel, user=user, action="rollback_backup", note="Stand vor lokalem Rollback")

    content = read_local_version(site, rel, version_id)
    live_file.parent.mkdir(parents=True, exist_ok=True)
    live_file.write_text(content, encoding="utf-8")
    return {
        "area": site,
        "file": rel.as_posix(),
        "version_id": Path(str(version_id)).name,
        "path": live_file.relative_to(repo_root).as_posix(),
    }
