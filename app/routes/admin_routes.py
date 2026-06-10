from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Form, Body
from fastapi.responses import RedirectResponse
from pathlib import Path
from typing import List, Dict, Any, Optional
import datetime
import posixpath
import re
import shutil
import traceback
import subprocess
from pydantic import BaseModel

from app.auth.deps import require_role, CurrentUser
from app.services.version_service import get_version, set_version
from app.services.build_service import (
    git_commit_and_push_docs, git_commit_and_push_paths, publish_flow, pdf_flow, mkdocs_build,
    REPO_ROOT, GIT_REMOTE, GIT_BRANCH
)
from app.services.log_service import (
    append_log, read_log, query_log,
    ACTION_APPROVED, ACTION_REJECTED
)
from app.services.pages_service import (
    sync_live_pages_for_item, cleanup_draft_pages_for_rejected_item, _remove_entry_for_rel,
    list_folder_paths, list_pages_order, save_pages_order, safe_rel_dir,
)
from app.services.local_versions_service import (
    create_local_version, list_local_versions, read_local_version, rollback_to_local_version,
)
from app.site_registry import SITE_KEY_SET, SITE_KEYS, normalize_site, site_folder

router = APIRouter(prefix="/admin", tags=["admin"])

SITES_ROOT = Path("sites")
ALLOWED_ADMIN_SITES = SITE_KEY_SET

MD_IMAGE_RE = re.compile(r'(!\[[^\]]*\]\()([^) \t]+)((?:[ \t][^)]*)?\))')
MD_LINK_RE = re.compile(r'(?<!!)(\[[^\]]+\]\()([^) \t]+)((?:[ \t][^)]*)?\))')
HTML_IMAGE_RE = re.compile(r'(<img\b[^>]*\bsrc=)(["\'])([^"\']+)(\2)', re.IGNORECASE)
HTML_LINK_RE = re.compile(r'(<a\b[^>]*\bhref=)(["\'])([^"\']+)(\2)', re.IGNORECASE)


# ----------------- Git helpers (Git nur fuer explizite Backup-/Rollback-Aktionen) -----------------
def _run_git(args: list[str]) -> tuple[bool, str]:
    p = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    out = (p.stdout or "") + ("\n" + (p.stderr or "") if p.stderr else "")
    return p.returncode == 0, (out.strip() or "")


def _git_require_ok(args: list[str]) -> str:
    ok, out = _run_git(args)
    if not ok:
        raise HTTPException(status_code=500, detail=out or "git failed")
    return out


def _git_show(ref_path: str) -> Optional[str]:
    # ref_path like: "main:sites/xxx/docs_draft/file.md"
    ok, out = _run_git(["show", ref_path])
    if not ok:
        return None
    return out


def _git_last_change_iso(branch: str, path: str) -> str:
    ok, out = _run_git(["log", "-1", "--format=%cI", branch, "--", path])
    if ok and out.strip():
        return out.strip()
    return ""


# ----------------- Other helpers -----------------
def _log_area_for_entry(entry: Dict[str, Any]) -> str:
    details = entry.get("details")
    if not isinstance(details, dict):
        details = {}
    area = (
        entry.get("area")
        or entry.get("site")
        or details.get("area")
        or details.get("site")
        or ""
    )
    return str(area).strip().lower()
def _split_area_file(area: str | None, file: str) -> tuple[str, str]:
    raw_area = (area or "").strip()
    try:
        a = normalize_site(raw_area) if raw_area else ""
    except KeyError:
        a = raw_area.lower()
    f = (file or "").strip()

    if not a and ":" in f:
        maybe_a, maybe_f = f.split(":", 1)
        if maybe_a and maybe_f:
            a = maybe_a.strip().lower()
            f = maybe_f.strip()

    if not a:
        raise HTTPException(status_code=400, detail="area fehlt")
    if not f:
        raise HTTPException(status_code=400, detail="file fehlt")

    return a, f


def _safe_rel_md(path: str) -> Path:
    p = (path or "").strip().replace("\\", "/")
    if not p.lower().endswith(".md"):
        p += ".md"
    rel = Path(p)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Ungültiger Dateipfad (nur relative .md)")
    return rel


def _repo_live_path(area: str, rel_md: Path) -> str:
    return (SITES_ROOT / site_folder(area) / "docs" / rel_md).as_posix()


def _repo_draft_path(area: str, rel_md: Path) -> str:
    return (SITES_ROOT / site_folder(area) / "docs_draft" / rel_md).as_posix()


def _repo_path_for_kind(area: str, rel_md: Path, kind: str) -> str:
    k = (kind or "live").strip().lower()
    if k == "live":
        return _repo_live_path(area, rel_md)
    if k == "draft":
        return _repo_draft_path(area, rel_md)
    raise HTTPException(status_code=400, detail="kind muss 'live' oder 'draft' sein")


def _fs_live_path(area: str, rel_md: Path) -> Path:
    return REPO_ROOT / _repo_live_path(area, rel_md)


def _fs_draft_path(area: str, rel_md: Path) -> Path:
    return REPO_ROOT / _repo_draft_path(area, rel_md)


def _is_external_or_special_url(value: str) -> bool:
    url = (value or "").strip()
    return url.startswith(("http://", "https://", "data:", "#", "mailto:", "tel:"))


def _normalize_asset_links(text: str, rel_md: Path) -> str:
    """
    MkDocs wertet relative Links relativ zur aktuellen Markdown-Datei aus.
    Ein Link assets/... muss in Unterordnern daher zu ../assets/... werden.
    """
    parent = rel_md.parent.as_posix()
    if parent in {"", "."}:
        return text

    def normalize_url(url: str) -> str:
        clean = (url or "").strip().strip('"').strip("'")
        if _is_external_or_special_url(clean) or clean.startswith("/"):
            return url
        if not clean.startswith("assets/"):
            return url
        return posixpath.relpath(clean, start=parent)

    def md_repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{normalize_url(match.group(2))}{match.group(3)}"

    def html_repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{match.group(2)}{normalize_url(match.group(3))}{match.group(4)}"

    text = MD_IMAGE_RE.sub(md_repl, text)
    text = MD_LINK_RE.sub(md_repl, text)
    text = HTML_IMAGE_RE.sub(html_repl, text)
    return HTML_LINK_RE.sub(html_repl, text)


def _asset_links_from_markdown(text: str) -> list[str]:
    urls: list[str] = []
    urls.extend(match.group(2) for match in MD_IMAGE_RE.finditer(text or ""))
    urls.extend(match.group(2) for match in MD_LINK_RE.finditer(text or ""))
    urls.extend(match.group(3) for match in HTML_IMAGE_RE.finditer(text or ""))
    urls.extend(match.group(3) for match in HTML_LINK_RE.finditer(text or ""))
    return urls


def _resolve_asset_rel(rel_md: Path, url: str) -> Path | None:
    clean = (url or "").strip().strip('"').strip("'")
    if not clean or _is_external_or_special_url(clean) or clean.startswith("/"):
        return None
    path_part = clean.split("#", 1)[0].split("?", 1)[0].strip()
    if not path_part:
        return None
    base = rel_md.parent.as_posix()
    joined = posixpath.normpath(posixpath.join(base, path_part)) if base not in {"", "."} else posixpath.normpath(path_part)
    if joined.startswith("../") or joined == "..":
        return None
    return Path(joined)


def _copy_referenced_draft_assets(area: str, rel_md: Path, markdown: str) -> list[str]:
    copied: list[str] = []
    site_root = REPO_ROOT / "sites" / site_folder(area)
    draft_root = site_root / "docs_draft"
    live_root = site_root / "docs"
    for url in _asset_links_from_markdown(markdown):
        asset_rel = _resolve_asset_rel(rel_md, url)
        if asset_rel is None:
            continue
        src = draft_root / asset_rel
        if not src.exists() or not src.is_file():
            continue
        dst = live_root / asset_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(dst.relative_to(REPO_ROOT).as_posix())
    return list(dict.fromkeys(copied))


def _prepare_approved_markdown(area: str, rel_md: Path, markdown: str) -> tuple[str, list[str]]:
    normalized = _normalize_asset_links(markdown, rel_md)
    copied = _copy_referenced_draft_assets(area, rel_md, normalized)
    return normalized, copied


def _read_fs_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _list_descendant_files(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )


def _coalesce_review_file(kind: str, path_value: str) -> str:
    value = (path_value or "").strip().replace("\\", "/").strip("/")
    if not value:
        return ""
    if kind == "folder":
        return f"{value}/index.md"
    if value.lower().endswith(".md"):
        return value
    return f"{value}.md"


def _coalesce_folder_path(path_value: str) -> Path:
    value = (path_value or "").strip().replace("\\", "/").strip("/")
    if value.lower().endswith("/index.md"):
        value = value[:-len("/index.md")]
    elif value.lower() == "index.md":
        value = ""
    return Path("." if value in {"", "."} else value)


def _log_change_key(entry: Dict[str, Any]) -> str:
    details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
    area = _log_area_for_entry(entry)
    action = (entry.get("action") or "").strip().lower()
    operation = str(details.get("operation") or "").strip().lower()
    kind = str(details.get("kind") or "").strip().lower()
    file_value = str(entry.get("file") or "").strip()

    if operation in {"moved", "renamed"}:
        anchor = str(details.get("to") or file_value).strip()
        return f"{area}|{operation}|{kind}|{anchor}"
    if operation == "deleted":
        anchor = str(details.get("path") or file_value).strip()
        return f"{area}|deleted|{kind}|{anchor}"
    if operation in {"file_created", "folder_created"}:
        anchor = str(details.get("path") or file_value).strip()
        created_kind = "folder" if operation == "folder_created" else "file"
        return f"{area}|{operation}|{created_kind}|{anchor}"
    return f"{area}|{action}|{file_value}"


def _change_item_from_log(entry: Dict[str, Any]) -> Dict[str, Any]:
    details = entry.get("details") if isinstance(entry.get("details"), dict) else {}
    area = _log_area_for_entry(entry)
    operation = str(details.get("operation") or "").strip().lower()
    kind = str(details.get("kind") or ("folder" if operation == "folder_created" else "file")).strip().lower()
    file_value = str(entry.get("file") or "").strip()
    path_value = (
        str(details.get("to") or details.get("path") or file_value).strip()
        if operation in {"moved", "renamed", "deleted", "file_created", "folder_created"}
        else file_value
    )
    review_file = _coalesce_review_file(kind, path_value)
    return {
        "area": area,
        "file": review_file or path_value,
        "display_file": path_value or review_file,
        "timestamp": entry.get("timestamp") or "",
        "user": entry.get("user") or "unbekannt",
        "action": entry.get("action") or "",
        "operation": operation,
        "kind": kind or "file",
        "from": str(details.get("from") or "").strip(),
        "to": str(details.get("to") or "").strip(),
        "path": str(details.get("path") or "").strip(),
        "source_origin": str(details.get("source_origin") or "").strip(),
        "details": details,
        "change_key": _log_change_key(entry),
    }


def _pending_log_changes() -> Dict[str, Dict[str, Any]]:
    pending: Dict[str, Dict[str, Any]] = {}
    for entry in read_log():
        key = _log_change_key(entry)
        action = (entry.get("action") or "").strip().lower()
        if action == "draft_saved":
            item = _change_item_from_log(entry)
            if item.get("operation"):
                pending[key] = item
        elif action in {"approved", "rejected"}:
            pending.pop(key, None)
    return pending


def _draft_item_covered_by_pending_op(item: Dict[str, Any], pending_ops: Dict[str, Dict[str, Any]]) -> bool:
    area = str(item.get("area") or "").strip().lower()
    file_value = str(item.get("file") or "").strip().replace("\\", "/").strip("/")
    if not area or not file_value:
        return False

    for op_item in pending_ops.values():
        if str(op_item.get("area") or "").strip().lower() != area:
            continue

        operation = str(op_item.get("operation") or "").strip().lower()
        kind = str(op_item.get("kind") or "file").strip().lower()
        target = str(op_item.get("to") or op_item.get("path") or op_item.get("file") or "").strip().replace("\\", "/").strip("/")

        if not operation or not target:
            continue

        if kind == "folder":
            folder_prefix = f"{target}/"
            if file_value == f"{target}/index.md" or file_value.startswith(folder_prefix):
                return True
        elif file_value == target:
            return True

    return False


def _list_local_drafts() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for site in SITE_KEYS:
        area_dir = REPO_ROOT / "sites" / site_folder(site)
        if not area_dir.is_dir():
            continue
        drafts_dir = area_dir / "docs_draft"
        if not drafts_dir.exists():
            continue
        for draft_path in drafts_dir.rglob("*.md"):
            stat = draft_path.stat()
            items.append({
                "area": site,
                "file": draft_path.relative_to(drafts_dir).as_posix(),
                "timestamp": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                "user": "unbekannt",
            })
    return items

def _uname(user: CurrentUser) -> str:
    if isinstance(user, dict):
        return (user.get("name") or user.get("username") or "admin").strip()
    return (getattr(user, "name", None) or getattr(user, "username", None) or "admin").strip()


class GitRollbackPayload(BaseModel):
    area: str
    file: str
    target: str        # commit hash
    kind: str = "live"  # live|draft
    user: str | None = None


class LocalRollbackPayload(BaseModel):
    area: str
    file: str
    version_id: str
    user: str | None = None


class SortOrderPayload(BaseModel):
    area: str
    folder: str = ""
    order: list[str]


def _safe_site(area: str) -> str:
    try:
        value = normalize_site(area)
    except KeyError:
        value = ""
    if value not in ALLOWED_ADMIN_SITES:
        raise HTTPException(status_code=400, detail="ungueltiger Bereich")
    return value


def _try_create_local_version(
    details: Dict[str, Any],
    area: str,
    rel: Path,
    user: CurrentUser,
    action: str,
    note: str,
) -> None:
    try:
        version = create_local_version(REPO_ROOT, area, rel, user=user, action=action, note=note)
        if version:
            details["local_version"] = version.get("version_id")
    except Exception as exc:
        details["local_version_error"] = str(exc)


def _snapshot_live_markdown_tree(area: str, folder_rel: Path, user: CurrentUser, action: str, note: str) -> list[str]:
    site = _safe_site(area)
    live_folder = REPO_ROOT / "sites" / site_folder(site) / "docs" / folder_rel
    if not live_folder.exists() or not live_folder.is_dir():
        return []

    versions: list[str] = []
    for md_path in sorted(live_folder.rglob("*.md")):
        rel = md_path.relative_to(REPO_ROOT / "sites" / site_folder(site) / "docs")
        try:
            version = create_local_version(REPO_ROOT, site, rel, user=user, action=action, note=note)
            if version:
                versions.append(version.get("version_id") or "")
        except Exception:
            continue
    return [v for v in versions if v]


# ----------------- Routes -----------------
@router.get("/ping")
def ping():
    return {"ok": True, "at": datetime.datetime.now().isoformat(timespec="seconds")}


@router.get("/changes")
def list_changes(user: CurrentUser = Depends(require_role("admin"))):
    pending_ops = _pending_log_changes()
    items = [
        it for it in _list_local_drafts()
        if not _draft_item_covered_by_pending_op(it, pending_ops)
    ]

    # Enrichment: letzten draft_saved pro Datei aus Log (User/Time/Meta)
    try:
        log = read_log()
        latest_by_key: Dict[str, Dict[str, Any]] = {}
        for e in reversed(log):
            if e.get("action") != "draft_saved":
                continue
            f = (e.get("file") or "").strip()
            a = _log_area_for_entry(e)
            if not f or not a:
                continue
            key = f"{a}:{f}"
            if key not in latest_by_key:
                latest_by_key[key] = e

        for it in items:
            meta = latest_by_key.get(f"{it['area']}:{it['file']}")
            if meta:
                it["user"] = meta.get("user", it["user"])
                it["timestamp"] = meta.get("timestamp", it["timestamp"])
                details = meta.get("details") if isinstance(meta.get("details"), dict) else {}
                it["operation"] = str(details.get("operation") or "").strip().lower()
                it["kind"] = str(details.get("kind") or "file").strip().lower()
                it["from"] = str(details.get("from") or "").strip()
                it["to"] = str(details.get("to") or "").strip()
                it["path"] = str(details.get("path") or "").strip()
                it["source_origin"] = str(details.get("source_origin") or "").strip()
                it["display_file"] = it.get("to") or it.get("path") or it["file"]
                it["change_key"] = _log_change_key(meta)
    except Exception:
        pass

    existing_keys = {str(it.get("change_key") or f"{it['area']}|draft_saved|{it['file']}") for it in items}
    existing_refs = {f"{it['area']}:{it['file']}" for it in items if it.get("area") and it.get("file")}
    for key, item in pending_ops.items():
        ref = f"{item.get('area')}:{item.get('file')}"
        if key in existing_keys or ref in existing_refs:
            continue
        items.append(item)

    # newest first
    items.sort(key=lambda x: x.get("timestamp") or "", reverse=True)
    return {"ok": True, "items": items}


@router.get("/history")
def history(
    action: str = Query(""),
    area: str = Query(""),
    file: str = Query(""),
    user: str = Query(""),
    limit: int = Query(200, ge=1, le=1000),
    current: CurrentUser = Depends(require_role("admin")),
):
    all_items = read_log()
    out: List[Dict[str, Any]] = []

    for e in reversed(all_items):
        a = e.get("action") or ""
        entry_area = _log_area_for_entry(e)
        details = e.get("details") if isinstance(e.get("details"), dict) else {}
        f = e.get("file") or ""
        u = str(e.get("user") or "")
        search_text = " ".join(
            str(value or "")
            for value in (
                f,
                entry_area,
                a,
                u,
                details.get("area"),
                details.get("site"),
                details.get("operation"),
                details.get("kind"),
                details.get("from"),
                details.get("to"),
                details.get("path"),
                details.get("comment"),
                details.get("draft_id"),
                details.get("repo_path"),
                details.get("target"),
            )
        ).lower()

        if action and a != action:
            continue
        if area and area.lower() != entry_area:
            continue
        if file and file.lower() not in search_text:
            continue
        if user and user.lower() not in u.lower():
            continue
        if a not in ("approved", "rejected", "draft_saved", "git_rollback", "local_rollback", "sort_saved"):
            continue

        out.append(e)
        if len(out) >= limit:
            break

    return {"ok": True, "items": out}


@router.get("/order/folders")
def order_folders(
    area: str = Query(...),
    user: CurrentUser = Depends(require_role("admin")),
):
    site = _safe_site(area)
    return {"ok": True, "area": site, "folders": list_folder_paths(REPO_ROOT, site)}


@router.get("/order")
def get_order(
    area: str = Query(...),
    folder: str = Query(""),
    user: CurrentUser = Depends(require_role("admin")),
):
    site = _safe_site(area)
    rel_dir = safe_rel_dir(folder)
    data = list_pages_order(REPO_ROOT, site, rel_dir)
    return {"ok": True, "area": site, **data}


@router.post("/order")
def save_order(
    payload: SortOrderPayload,
    user: CurrentUser = Depends(require_role("admin")),
):
    site = _safe_site(payload.area)
    rel_dir = safe_rel_dir(payload.folder)
    touched = save_pages_order(REPO_ROOT, site, rel_dir, payload.order)
    append_log(
        "",
        user,
        "sort_saved",
        {
            "area": site,
            "storage": "local",
            "folder": "" if str(rel_dir) in {"", "."} else rel_dir.as_posix(),
            "order": payload.order,
            "paths": touched,
            "publish_pending": True,
        },
    )
    saved = list_pages_order(REPO_ROOT, site, rel_dir)
    return {
        "ok": True,
        "area": site,
        "folder": payload.folder,
        "paths": touched,
        "order": saved.get("arrange") or [],
        "publish_pending": True,
    }


@router.get("/diff")
def get_diff(
    area: str = Query(""),
    file: str = Query(...),
    operation: str = Query(""),
    kind: str = Query("file"),
    from_path: str = Query(""),
    to_path: str = Query(""),
    path: str = Query(""),
    user: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)

    op = (operation or "").strip().lower()
    kind_norm = (kind or "file").strip().lower()

    if op == "deleted":
        target_rel = _safe_rel_md(_coalesce_review_file(kind_norm, path or file))
        live_path = _fs_live_path(area, target_rel)
        live_txt = _read_fs_text(live_path)
        return {"ok": True, "area": area, "file": target_rel.as_posix(), "live": live_txt, "draft": ""}

    target_rel = _safe_rel_md((to_path or file) if kind_norm == "file" else file)
    draft_path = _fs_draft_path(area, target_rel)
    live_path = _fs_live_path(area, target_rel)

    draft_txt = _read_fs_text(draft_path)
    live_txt = _read_fs_text(live_path)
    if op in {"moved", "renamed"} and not live_txt and from_path:
        source_rel = _safe_rel_md(_coalesce_review_file(kind_norm, from_path))
        live_txt = _read_fs_text(_fs_live_path(area, source_rel))
    if not draft_path.exists() and not op:
        raise HTTPException(status_code=404, detail="Draft nicht gefunden")
    return {"ok": True, "area": area, "file": target_rel.as_posix(), "live": live_txt, "draft": draft_txt}


@router.get("/change_preview")
def change_preview(
    area: str = Query(""),
    file: str = Query(...),
    operation: str = Query(""),
    kind: str = Query("file"),
    from_path: str = Query(""),
    to_path: str = Query(""),
    path: str = Query(""),
    source_origin: str = Query(""),
    user: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(area, file)
    op = (operation or "").strip().lower()
    kind_norm = (kind or "file").strip().lower()
    src_origin = (source_origin or "").strip().lower()
    files: list[str] = []

    if kind_norm == "folder":
        folder_rel = Path(".")
        if op == "deleted":
            folder_rel = _coalesce_folder_path(path or file)
            root = (REPO_ROOT / "sites" / site_folder(area) / ("docs" if src_origin == "live" else "docs_draft") / folder_rel)
            files = _list_descendant_files(root)
        elif op in {"moved", "renamed"}:
            if src_origin == "live":
                folder_rel = _coalesce_folder_path(from_path or path or file)
                root = REPO_ROOT / "sites" / site_folder(area) / "docs" / folder_rel
            else:
                folder_rel = _coalesce_folder_path(to_path or path or file)
                root = REPO_ROOT / "sites" / site_folder(area) / "docs_draft" / folder_rel
            files = _list_descendant_files(root)

    return {
        "ok": True,
        "area": area,
        "file": file,
        "operation": op,
        "kind": kind_norm,
        "from": (from_path or "").strip(),
        "to": (to_path or "").strip(),
        "path": (path or "").strip(),
        "source_origin": src_origin,
        "files": files,
    }


@router.post("/approve")
def approve(
    area: str = Form(""),
    file: str = Form(...),
    operation: str = Form(""),
    kind: str = Form("file"),
    from_path: str = Form(""),
    to_path: str = Form(""),
    path: str = Form(""),
    source_origin: str = Form(""),
    user: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)
    op = (operation or "").strip().lower()
    kind_norm = (kind or "file").strip().lower()
    details: Dict[str, Any] = {
        "area": area,
        "storage": "local",
        "operation": op,
        "kind": kind_norm,
        "from": (from_path or "").strip(),
        "to": (to_path or "").strip(),
        "path": (path or "").strip(),
        "source_origin": (source_origin or "").strip(),
        "publish_pending": True,
    }

    try:
        if op in {"moved", "renamed"}:
            target_rel = _safe_rel_md(to_path or file)
            target_draft = _fs_draft_path(area, target_rel)
            target_live = _fs_live_path(area, target_rel)
            source_rel = _safe_rel_md(from_path) if from_path else None
            source_live = _fs_live_path(area, source_rel) if source_rel else None

            if kind_norm == "file":
                if not target_draft.exists():
                    raise HTTPException(status_code=404, detail="Ziel-Draft nicht gefunden")
                target_live.parent.mkdir(parents=True, exist_ok=True)
                approved_text, copied_assets = _prepare_approved_markdown(area, target_rel, target_draft.read_text(encoding="utf-8"))
                target_live.write_text(approved_text, encoding="utf-8")
                if copied_assets:
                    details["assets"] = copied_assets
                sync_live_pages_for_item(REPO_ROOT, area, target_rel)
                _try_create_local_version(details, area, target_rel, user, "approved", op or "moved_or_renamed")
                if source_rel:
                    _remove_entry_for_rel(REPO_ROOT, area, source_rel, prefer_draft=False)
                if source_live and source_live.exists() and source_live != target_live:
                    source_live.unlink()
                _remove_entry_for_rel(REPO_ROOT, area, target_rel, prefer_draft=True)
                if target_draft.exists():
                    target_draft.unlink()
            else:
                target_folder_rel = Path((to_path or path or "").strip().replace("\\", "/").strip("/"))
                if str(target_folder_rel) in {"", "."}:
                    raise HTTPException(status_code=400, detail="Zielordner fehlt")
                target_draft = REPO_ROOT / "sites" / site_folder(area) / "docs_draft" / target_folder_rel
                target_live = REPO_ROOT / "sites" / site_folder(area) / "docs" / target_folder_rel
                if not target_draft.exists():
                    raise HTTPException(status_code=404, detail="Ziel-Draft-Ordner nicht gefunden")
                shutil.copytree(target_draft, target_live, dirs_exist_ok=True)
                sync_live_pages_for_item(REPO_ROOT, area, target_folder_rel / "index.md")
                versions = _snapshot_live_markdown_tree(area, target_folder_rel, user, "approved", op or "folder_moved_or_renamed")
                if versions:
                    details["local_versions"] = versions
                if from_path:
                    _remove_entry_for_rel(REPO_ROOT, area, Path(from_path.strip()) / "index.md", prefer_draft=False)
                    source_live_folder = REPO_ROOT / "sites" / site_folder(area) / "docs" / Path(from_path.strip().replace("\\", "/").strip("/"))
                    if source_live_folder.exists() and source_live_folder != target_live:
                        shutil.rmtree(source_live_folder, ignore_errors=True)
                _remove_entry_for_rel(REPO_ROOT, area, target_folder_rel / "index.md", prefer_draft=True)
                shutil.rmtree(target_draft, ignore_errors=True)
        elif op == "deleted":
            target_rel = _safe_rel_md(path or file)
            live_fs = _fs_live_path(area, target_rel)
            if kind_norm == "file":
                if live_fs.exists():
                    _try_create_local_version(details, area, target_rel, user, "delete_approved", "Stand vor Freigabe der Loeschung")
                    _remove_entry_for_rel(REPO_ROOT, area, target_rel, prefer_draft=False)
                    live_fs.unlink()
            else:
                folder_rel = Path((path or "").strip().replace("\\", "/").strip("/"))
                live_folder = REPO_ROOT / "sites" / site_folder(area) / "docs" / folder_rel
                _remove_entry_for_rel(REPO_ROOT, area, folder_rel / "index.md", prefer_draft=False)
                if live_folder.exists():
                    versions = _snapshot_live_markdown_tree(area, folder_rel, user, "delete_approved", "Stand vor Freigabe der Ordner-Loeschung")
                    if versions:
                        details["local_versions"] = versions
                    shutil.rmtree(live_folder, ignore_errors=True)
        elif op == "folder_created" and kind_norm == "folder":
            folder_rel = _coalesce_folder_path(path or to_path or "")
            if str(folder_rel) in {"", "."}:
                raise HTTPException(status_code=400, detail="Ordnerpfad fehlt")
            draft_folder = REPO_ROOT / "sites" / site_folder(area) / "docs_draft" / folder_rel
            live_folder = REPO_ROOT / "sites" / site_folder(area) / "docs" / folder_rel
            if not draft_folder.exists():
                raise HTTPException(status_code=404, detail="Draft-Ordner nicht gefunden")
            shutil.copytree(draft_folder, live_folder, dirs_exist_ok=True)
            sync_live_pages_for_item(REPO_ROOT, area, folder_rel / "index.md")
            versions = _snapshot_live_markdown_tree(area, folder_rel, user, "approved", "folder_created")
            if versions:
                details["local_versions"] = versions
            shutil.rmtree(draft_folder, ignore_errors=True)
        elif op == "file_created":
            target_rel = _safe_rel_md(path or file)
            draft_fs = _fs_draft_path(area, target_rel)
            live_fs = _fs_live_path(area, target_rel)
            if not draft_fs.exists():
                raise HTTPException(status_code=404, detail="Draft nicht gefunden")
            live_fs.parent.mkdir(parents=True, exist_ok=True)
            approved_text, copied_assets = _prepare_approved_markdown(area, target_rel, draft_fs.read_text(encoding="utf-8"))
            live_fs.write_text(approved_text, encoding="utf-8")
            if copied_assets:
                details["assets"] = copied_assets
            sync_live_pages_for_item(REPO_ROOT, area, target_rel)
            _try_create_local_version(details, area, target_rel, user, "approved", op or "file")
            draft_fs.unlink()
        else:
            draft_fs = _fs_draft_path(area, rel)
            live_fs = _fs_live_path(area, rel)
            if not draft_fs.exists():
                raise HTTPException(status_code=404, detail="Draft nicht gefunden")

            live_fs.parent.mkdir(parents=True, exist_ok=True)
            approved_text, copied_assets = _prepare_approved_markdown(area, rel, draft_fs.read_text(encoding="utf-8"))
            live_fs.write_text(approved_text, encoding="utf-8")
            draft_fs.unlink()

            details = {
                "area": area,
                "storage": "local",
                "publish_pending": True,
            }
            if copied_assets:
                details["assets"] = copied_assets
            _try_create_local_version(details, area, rel, user, "approved", "file")

        append_log(rel.as_posix(), user, ACTION_APPROVED, details)

        return {"ok": True, "storage": "local", "publish_pending": True}

    except HTTPException:
        append_log(rel.as_posix(), user, ACTION_APPROVED, details)
        raise
    except Exception as e:
        error_details = dict(details)
        error_details["error"] = str(e)
        append_log(rel.as_posix(), user, ACTION_APPROVED, error_details)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject")
def reject(
    area: str = Form(""),
    file: str = Form(...),
    operation: str = Form(""),
    kind: str = Form("file"),
    from_path: str = Form(""),
    to_path: str = Form(""),
    path: str = Form(""),
    source_origin: str = Form(""),
    user: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)
    op = (operation or "").strip().lower()
    kind_norm = (kind or "file").strip().lower()
    details: Dict[str, Any] = {
        "area": area,
        "storage": "local",
        "operation": op,
        "kind": kind_norm,
        "from": (from_path or "").strip(),
        "to": (to_path or "").strip(),
        "path": (path or "").strip(),
        "source_origin": (source_origin or "").strip(),
    }

    try:
        if op in {"moved", "renamed"}:
            if kind_norm == "file":
                target_rel = _safe_rel_md(to_path or file)
                target_draft = _fs_draft_path(area, target_rel)
                if target_draft.exists():
                    _remove_entry_for_rel(REPO_ROOT, area, target_rel, prefer_draft=True)
                    target_draft.unlink()
            else:
                target_folder_rel = Path((to_path or path or "").strip().replace("\\", "/").strip("/"))
                if str(target_folder_rel) not in {"", "."}:
                    _remove_entry_for_rel(REPO_ROOT, area, target_folder_rel / "index.md", prefer_draft=True)
                    shutil.rmtree(REPO_ROOT / "sites" / site_folder(area) / "docs_draft" / target_folder_rel, ignore_errors=True)
        elif op == "deleted":
            details["note"] = "Löschung nicht übernommen"
        elif op == "folder_created" and kind_norm == "folder":
            folder_rel = _coalesce_folder_path(path or to_path or "")
            if str(folder_rel) not in {"", "."}:
                cleanup_draft_pages_for_rejected_item(REPO_ROOT, area, folder_rel / "index.md")
                shutil.rmtree(REPO_ROOT / "sites" / site_folder(area) / "docs_draft" / folder_rel, ignore_errors=True)
        elif op == "file_created":
            target_rel = _safe_rel_md(path or file)
            draft_fs = _fs_draft_path(area, target_rel)
            if draft_fs.exists():
                draft_fs.unlink()
            cleanup_draft_pages_for_rejected_item(REPO_ROOT, area, target_rel)
        else:
            draft_fs = _fs_draft_path(area, rel)
            if not draft_fs.exists():
                details["note"] = "Draft bereits gelöscht."
                append_log(rel.as_posix(), user, ACTION_REJECTED, details)
                return {"ok": True, "note": "Draft nicht vorhanden (bereits gelöscht)."}
            if draft_fs.exists():
                draft_fs.unlink()

        append_log(rel.as_posix(), user, ACTION_REJECTED, details)

        return {"ok": True, "storage": "local"}

    except HTTPException:
        append_log(rel.as_posix(), user, ACTION_REJECTED, details)
        raise
    except Exception as e:
        error_details = dict(details)
        error_details["error"] = str(e)
        append_log(rel.as_posix(), user, ACTION_REJECTED, error_details)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/git/sync")
def git_sync(
    site: str = Query("all", description="all | schaden | betrieb | vertrieb | allgemein | buchhaltung | novas | datenschutz | wto | it-faq | testumgebung"),
    user: CurrentUser = Depends(require_role("admin")),
):
    raise HTTPException(status_code=410, detail="Inhalts-Sync nach Git ist deaktiviert.")
    normalized_site = (site or "all").strip().lower()
    if normalized_site != "all":
        try:
            normalized_site = normalize_site(normalized_site)
        except KeyError:
            pass
    if normalized_site != "all" and normalized_site not in ALLOWED_ADMIN_SITES:
        raise HTTPException(status_code=400, detail="ungueltige site")

    ok, output = git_commit_and_push_docs(
        f"Manual backup sync ({normalized_site}) {datetime.datetime.now().isoformat(timespec='seconds')}",
        site=normalized_site,
    )
    if not ok:
        raise HTTPException(status_code=500, detail=output)
    return {"ok": True, "site": normalized_site, "git": output}


# ---------- Multi-Site Build ----------
@router.post("/build_site")
def build_site(
    site: str = Query(..., description="schaden | betrieb | vertrieb | allgemein | buchhaltung | novas | datenschutz | wto | it-faq | testumgebung"),
    user: CurrentUser = Depends(require_role("admin")),
):
    ok, out = mkdocs_build(site=site, enable_pdf=False)
    if not ok:
        raise HTTPException(status_code=500, detail=out)
    return {"ok": True, "site": site, "output": out}


@router.post("/build_all")
def build_all(user: CurrentUser = Depends(require_role("admin"))):
    ok, out = mkdocs_build(site="all", enable_pdf=False)
    if not ok:
        raise HTTPException(status_code=500, detail=out)
    return {"ok": True, "site": "all", "output": out}


# ---------- Publish / PDF ----------
@router.post("/publish")
def admin_publish(
    site: str = Query("all", description="all | schaden | betrieb | vertrieb | allgemein | buchhaltung | novas | datenschutz | wto | it-faq | testumgebung"),
    payload: dict = Body(default={}),
    user: CurrentUser = Depends(require_role("admin")),
):
    new_version = (payload or {}).get("version")
    try:
        return publish_flow(new_version=new_version, site=site)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pdf")
def admin_pdf(
    site: str = Query("all", description="all | schaden | betrieb | vertrieb | allgemein | buchhaltung | novas | datenschutz | wto | it-faq | testumgebung"),
    user: CurrentUser = Depends(require_role("admin")),
):
    try:
        return pdf_flow(site=site)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




@router.get("/pdf/open")
def admin_pdf_open(
    site: str = Query("all", description="all | schaden | betrieb | vertrieb | allgemein | buchhaltung | novas | datenschutz | wto | it-faq | testumgebung"),
    user: CurrentUser = Depends(require_role("admin")),
):
    try:
        data = pdf_flow(site=site)
        pdf_url = str(data.get("pdf_url") or "").strip()
        if not pdf_url:
            raise HTTPException(status_code=500, detail="PDF wurde erzeugt, aber keine PDF-URL gefunden.")
        return RedirectResponse(url=pdf_url, status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/version")
def version_get(user: CurrentUser = Depends(require_role("editor"))):
    return get_version(site="portal")


@router.post("/version")
def version_set(new_version: str = Form(...), user: CurrentUser = Depends(require_role("admin"))):
    return set_version(new_version, site="portal", mirror_to_sites=True)


# ---------------- Lokale Versionen / Rollback ----------------
@router.get("/local_versions/history")
def local_versions_history(
    area: str = Query(...),
    file: str = Query(...),
    limit: int = Query(50, ge=1, le=200),
    current: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)
    versions = list_local_versions(area, rel, limit=limit)
    return {
        "ok": True,
        "area": area,
        "file": rel.as_posix(),
        "kind": "local",
        "versions": versions,
    }


@router.get("/local_versions/diff")
def local_versions_diff(
    area: str = Query(...),
    file: str = Query(...),
    version_id: str = Query(...),
    current: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)
    current_text = _read_fs_text(_fs_live_path(area, rel))
    old_text = read_local_version(area, rel, version_id)
    return {
        "ok": True,
        "area": area,
        "file": rel.as_posix(),
        "kind": "local",
        "version_id": version_id,
        "current_text": current_text,
        "old_text": old_text,
    }


@router.post("/local_versions/rollback")
def local_versions_rollback(
    payload: LocalRollbackPayload,
    current: CurrentUser = Depends(require_role("admin")),
):
    area, file = _split_area_file(payload.area, payload.file)
    rel = _safe_rel_md(file)
    user_label = (payload.user or _uname(current)).strip()[:80]
    version_id = (payload.version_id or "").strip()
    if not version_id:
        raise HTTPException(status_code=400, detail="version_id fehlt")

    result = rollback_to_local_version(REPO_ROOT, area, rel, version_id, user=user_label)
    sync_live_pages_for_item(REPO_ROOT, area, rel)
    append_log(rel.as_posix(), current, "local_rollback", {
        "area": area,
        "kind": "live",
        "storage": "local",
        "version_id": version_id,
        "repo_path": result.get("path"),
        "publish_pending": True,
    })
    return {"ok": True, **result, "publish_pending": True}


# ---------------- Git Rollback deaktiviert: Inhalte duerfen nicht mehr ueber Git laufen ----------------
@router.get("/git/history")
def git_file_history(
    area: str = Query(...),
    file: str = Query(...),
    kind: str = Query("live", description="nur live unterstützt"),
    limit: int = Query(50, ge=1, le=200),
    current: CurrentUser = Depends(require_role("admin")),
):
    raise HTTPException(status_code=410, detail="Git-Rollback ist deaktiviert. Bitte lokales Rollback verwenden.")
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)

    requested_kind = (kind or "live").strip().lower()
    if requested_kind != "live":
        raise HTTPException(status_code=400, detail="Git-Rollback ist derzeit nur fuer veroeffentlichte Inhalte verfuegbar")

    def _read_commits(repo_path: str) -> list[dict[str, Any]]:
        out = _git_require_ok([
            "log",
            "--follow",
            f"-n{limit}",
            "--pretty=format:%H%x1f%an%x1f%ad%x1f%s",
            "--date=iso-strict",
            "--",
            repo_path
        ])

        commits: list[dict[str, Any]] = []
        if out.strip():
            for line in out.splitlines():
                h, a, d, s = line.split("\x1f")
                commits.append({"hash": h, "author": a, "date": d, "subject": s})
        return commits

    effective_kind = "live"
    repo_path = _repo_live_path(area, rel)
    commits = _read_commits(repo_path)

    return {
        "ok": True,
        "area": area,
        "file": rel.as_posix(),
        "kind": effective_kind,
        "requested_kind": requested_kind,
        "repo_path": repo_path,
        "commits": commits,
    }


@router.get("/git/diff")
def git_file_diff(
    area: str = Query(...),
    file: str = Query(...),
    kind: str = Query("live", description="nur live unterstützt"),
    a: str = Query(..., description="newer commit"),
    b: str = Query(..., description="older commit"),
    current: CurrentUser = Depends(require_role("admin")),
):
    raise HTTPException(status_code=410, detail="Git-Rollback ist deaktiviert. Bitte lokales Rollback verwenden.")
    area, file = _split_area_file(area, file)
    rel = _safe_rel_md(file)
    if (kind or "live").strip().lower() != "live":
        raise HTTPException(status_code=400, detail="Git-Rollback ist derzeit nur fuer veroeffentlichte Inhalte verfuegbar")
    repo_path = _repo_live_path(area, rel)

    txt = _git_require_ok(["diff", f"{b}..{a}", "--", repo_path])
    current_text = _read_fs_text(REPO_ROOT / repo_path)
    old_text = _git_show(f"{b}:{repo_path}") or ""
    return {
        "ok": True,
        "area": area,
        "file": rel.as_posix(),
        "kind": (kind or "live").strip().lower(),
        "a": a,
        "b": b,
        "diff": txt,
        "current_text": current_text,
        "old_text": old_text,
    }

@router.post("/git/rollback")
def git_file_rollback(
    payload: GitRollbackPayload,
    current: CurrentUser = Depends(require_role("admin")),
):
    raise HTTPException(status_code=410, detail="Git-Rollback ist deaktiviert. Bitte lokales Rollback verwenden.")
    area, file = _split_area_file(payload.area, payload.file)
    rel = _safe_rel_md(file)
    kind = (payload.kind or "live").strip().lower()
    if kind != "live":
        raise HTTPException(status_code=400, detail="Git-Rollback ist derzeit nur fuer veroeffentlichte Inhalte verfuegbar")
    repo_path = _repo_live_path(area, rel)

    user_label = (payload.user or getattr(current, "name", None) or getattr(current, "username", None) or "admin").strip()[:80]
    target = (payload.target or "").strip()
    if not target:
        raise HTTPException(status_code=400, detail="target fehlt")

    # Ziel-Commit validieren
    _git_require_ok(["rev-parse", "--verify", target])

    # Datei auf Ziel-Stand setzen; falls dort nicht vorhanden -> löschen
    exists_ok, _ = _run_git(["cat-file", "-e", f"{target}:{repo_path}"])
    if exists_ok:
        _git_require_ok(["restore", "--source", target, "--", repo_path])
    else:
        fs_path = REPO_ROOT / repo_path
        if fs_path.exists() and fs_path.is_file():
            fs_path.unlink()

    _git_require_ok(["add", "-A", "--", repo_path])

    staged = _git_require_ok(["diff", "--cached", "--name-only"]).strip()
    if not staged:
        return {
            "ok": True,
            "note": "Keine Änderung (Zielstand entspricht aktuellem Stand).",
            "area": area,
            "file": rel.as_posix(),
            "kind": kind,
        }

    msg = f"rollback({kind}/{area}): {rel.as_posix()} -> {target[:7]} by {user_label}"
    _git_require_ok(["commit", "-m", msg])
    _git_require_ok(["push", GIT_REMOTE, "main"])

    new_head = _git_require_ok(["rev-parse", "HEAD"]).strip()
    append_log(rel.as_posix(), current, "git_rollback", {
        "area": area,
        "kind": kind,
        "repo_path": repo_path,
        "target": target,
        "new_head": new_head,
    })

    return {
        "ok": True,
        "area": area,
        "file": rel.as_posix(),
        "kind": kind,
        "target": target,
        "new_head": new_head,
    }



