from __future__ import annotations

from pathlib import Path
import posixpath
import re
import shutil
import traceback

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.auth.deps import CurrentUser, require_role
from app.services.build_service import REPO_ROOT
from app.services.log_service import append_log
from app.services.pages_service import create_draft_item, move_draft_item, delete_draft_item
from app.site_registry import SITE_KEY_SET, SITE_KEYS, site_folder, normalize_site

router = APIRouter(prefix="/editor", tags=["editor"])

SITES_ROOT = REPO_ROOT / "sites"

ALLOWED_SITES = SITE_KEY_SET
SITES = {site: {"root": SITES_ROOT / site_folder(site)} for site in ALLOWED_SITES}
ALLOWED_UPLOAD_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv",
}
IMAGE_UPLOAD_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}


def _safe_upload_filename(filename: str, dest_dir: Path) -> str:
    raw = Path(filename or "image").name.strip()
    stem = Path(raw).stem or "image"
    suffix = Path(raw).suffix.lower() or ".png"
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_") or "image"
    candidate = f"{safe_stem}{suffix}"
    i = 1
    while (dest_dir / candidate).exists():
        candidate = f"{safe_stem}_{i}{suffix}"
        i += 1
    return candidate


def _upload_kind(filename: str, content_type: str = "") -> str:
    suffix = Path(filename or "").suffix.lower()
    if suffix in IMAGE_UPLOAD_EXTENSIONS or str(content_type or "").lower().startswith("image/"):
        return "image"
    return "file"


def _ensure_allowed_upload(filename: str) -> None:
    suffix = Path(filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Dateityp nicht erlaubt. Erlaubt: {allowed}")


def _safe_rel(path: str) -> Path:
    value = (path or "").strip().replace("\\", "/")
    if not value.lower().endswith(".md"):
        value += ".md"
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Ungueltiger Dateipfad (nur relative .md)")
    return rel


def _safe_rel_path(path: str) -> Path:
    value = (path or "").strip().replace("\\", "/").strip("/")
    rel = Path(value) if value else Path(".")
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Ungueltiger relativer Pfad")
    return rel


def _strip_site_prefix(site: str, value: str) -> str:
    clean = (value or "").strip().replace("\\", "/").strip("/")
    site_key = normalize_site(site)
    site_dir = site_folder(site_key)
    if ":" in clean:
        maybe_site, maybe_path = clean.split(":", 1)
        if maybe_site.strip().lower() == site_key:
            clean = maybe_path.strip().replace("\\", "/").strip("/")
    prefixes = [
        f"sites/{site_key}/docs_draft/",
        f"sites/{site_key}/docs/",
        f"sites/{site_dir}/docs_draft/",
        f"sites/{site_dir}/docs/",
        f"{site_key}/docs_draft/",
        f"{site_key}/docs/",
        f"{site_dir}/docs_draft/",
        f"{site_dir}/docs/",
    ]
    lower = clean.lower()
    for prefix in prefixes:
        if lower.startswith(prefix):
            clean = clean[len(prefix):]
            break
    return clean.strip("/")


def _move_source_rel(site: str, source: str, kind: str) -> Path:
    clean = _strip_site_prefix(site, source)
    if (kind or "").strip().lower() == "file":
        return _safe_rel(clean)
    if clean.lower().endswith("/index.md"):
        clean = clean[:-len("/index.md")]
    elif clean.lower() == "index.md":
        clean = ""
    return _safe_rel_path(clean)


def _safe_name(name: str, *, folder: bool = False) -> str:
    value = (name or "").strip().replace("\\", "/").strip("/")
    if not value:
        raise HTTPException(status_code=400, detail="Name fehlt")
    if "/" in value or "\\" in value or value in {".", ".."}:
        raise HTTPException(status_code=400, detail="Ungueltiger Name")
    if not folder and not value.lower().endswith(".md"):
        value += ".md"
    return value


def _ensure_within(base: Path, target: Path) -> Path:
    resolved_base = base.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Pfad ausserhalb des erlaubten Bereichs")
    return resolved_target


def _all_markdown_folders(*roots: Path) -> list[str]:
    folders = {""}
    for root in roots:
        if not root.exists():
            continue
        for dir_path in root.rglob("*"):
            if not dir_path.is_dir():
                continue
            rel_dir = dir_path.relative_to(root).as_posix()
            if rel_dir.startswith("assets"):
                continue
            folders.add("" if rel_dir in {"", "."} else rel_dir)
        for md_path in root.rglob("*.md"):
            rel_parent = md_path.relative_to(root).parent.as_posix()
            current = Path(rel_parent) if rel_parent not in {"", "."} else Path(".")
            while True:
                folder = "" if str(current) in {"", "."} else current.as_posix()
                folders.add(folder)
                if folder == "":
                    break
                current = current.parent
    return sorted(folders)


def _draft_or_live_path(*, docs_dir: Path, drafts_dir: Path, rel: Path) -> tuple[Path, str]:
    draft_path = drafts_dir / rel
    if draft_path.exists():
        return draft_path, "draft"

    live_path = docs_dir / rel
    if live_path.exists():
        return live_path, "live"

    raise HTTPException(status_code=404, detail="Quelle nicht gefunden")


def _read_text_raw(path: Path) -> str:
    return path.read_bytes().decode("utf-8", errors="ignore")


def _list_descendant_files(root: Path) -> list[str]:
    if not root.exists() or not root.is_dir():
        return []
    return sorted(
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    )


def _resolve_site(site: str):
    try:
        normalized = normalize_site(site)
    except KeyError:
        normalized = ""
    if normalized not in SITES:
        raise HTTPException(status_code=400, detail="Ungueltige site")

    root = SITES[normalized]["root"]
    docs_dir = root / "docs"
    drafts_dir = root / "docs_draft"
    assets_dir = drafts_dir / "assets" / "images"

    for path in (docs_dir, drafts_dir, assets_dir):
        path.mkdir(parents=True, exist_ok=True)

    return docs_dir, drafts_dir, assets_dir


@router.get("/list")
async def list_files(
    site: str = Query(..., description="schaden|betrieb|vertrieb|allgemein|buchhaltung|novas|datenschutz|wto|it-faq|testumgebung"),
    user: CurrentUser = Depends(require_role("editor")),
):
    docs_dir, drafts_dir, _ = _resolve_site(site)

    files: dict[str, dict[str, str]] = {}
    for path in docs_dir.rglob("*.md"):
        rel = path.relative_to(docs_dir).as_posix()
        files[rel] = {"path": rel, "source": "live"}
    for path in drafts_dir.rglob("*.md"):
        rel = path.relative_to(drafts_dir).as_posix()
        files[rel] = {"path": rel, "source": "draft"}

    out = [{"path": key, "source": value["source"]} for key, value in sorted(files.items())]
    return {"ok": True, "site": site, "files": out}


@router.get("/list_all")
async def list_all_files(
    user: CurrentUser = Depends(require_role("editor")),
):
    out: list[dict[str, str]] = []

    for site in SITE_KEYS:
        docs_dir, drafts_dir, _ = _resolve_site(site)
        files: dict[str, dict[str, str]] = {}
        for path in docs_dir.rglob("*.md"):
            rel = path.relative_to(docs_dir).as_posix()
            files[rel] = {"path": rel, "source": "live"}
        for path in drafts_dir.rglob("*.md"):
            rel = path.relative_to(drafts_dir).as_posix()
            files[rel] = {"path": rel, "source": "draft"}

        for key, value in sorted(files.items()):
            out.append(
                {
                    "site": site,
                    "path": key,
                    "source": value["source"],
                    "label": f"{site} / {key}",
                }
            )

    return {"ok": True, "files": out}


@router.get("/load")
async def load(
    site: str = Query(...),
    file: str = Query(..., description="relativer Pfad z.B. einleitung/zweck.md"),
    user: CurrentUser = Depends(require_role("editor")),
):
    docs_dir, drafts_dir, _ = _resolve_site(site)

    rel = _safe_rel(file)
    draft_path = drafts_dir / rel
    live_path = docs_dir / rel

    if draft_path.exists():
        return {"ok": True, "site": site, "source": "draft", "content": _read_text_raw(draft_path)}
    if live_path.exists():
        return {"ok": True, "site": site, "source": "live", "content": _read_text_raw(live_path)}
    return {"ok": True, "site": site, "source": "new", "content": ""}


@router.post("/save")
async def save(
    site: str = Form(...),
    file: str = Form(...),
    markdown: str = Form(...),
    comment: str = Form(""),
    user: CurrentUser = Depends(require_role("editor")),
):
    _, drafts_dir, _ = _resolve_site(site)

    rel = _safe_rel(file)
    draft_path = drafts_dir / rel
    draft_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        draft_path.write_text(markdown, encoding="utf-8")
        append_log(
            rel.as_posix(),
            user,
            "draft_saved",
            {
                "area": site,
                "comment": (comment or "").strip(),
                "storage": "local",
            },
        )
        return {"ok": True, "site": site, "draft_id": rel.as_posix(), "storage": "local"}
    except HTTPException:
        raise
    except Exception as exc:
        print("Exception in /editor/save:", repr(exc))
        print(traceback.format_exc())
        try:
            append_log(
                rel.as_posix(),
                user,
                "draft_saved",
                {
                    "area": site,
                    "comment": (comment or "").strip(),
                    "storage": "local",
                    "error": str(exc),
                },
            )
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload_image")
async def upload_image(
    site: str = Form(...),
    file: str = Form(""),
    image: UploadFile = File(...),
    user: CurrentUser = Depends(require_role("editor")),
):
    _, _, assets_dir = _resolve_site(site)

    filename = _safe_upload_filename(image.filename or "image.png", assets_dir)
    dest_path = assets_dir / filename

    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
        asset_path = f"assets/images/{filename}"
        md_rel = _safe_rel(file) if (file or "").strip() else Path("index.md")
        md_dir = md_rel.parent.as_posix()
        rel_path = posixpath.relpath(asset_path, start=md_dir if md_dir not in {"", "."} else ".")
        return {"ok": True, "site": site, "path": rel_path}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.post("/upload_file")
async def upload_file(
    site: str = Form(...),
    file: str = Form(""),
    upload: UploadFile = File(...),
    user: CurrentUser = Depends(require_role("editor")),
):
    _, drafts_dir, _ = _resolve_site(site)
    original_name = upload.filename or "datei"
    _ensure_allowed_upload(original_name)

    kind = _upload_kind(original_name, upload.content_type or "")
    asset_folder = "images" if kind == "image" else "files"
    assets_dir = drafts_dir / "assets" / asset_folder
    assets_dir.mkdir(parents=True, exist_ok=True)

    filename = _safe_upload_filename(original_name, assets_dir)
    dest_path = assets_dir / filename

    try:
        with dest_path.open("wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        asset_path = f"assets/{asset_folder}/{filename}"
        md_rel = _safe_rel(file) if (file or "").strip() else Path("index.md")
        md_dir = md_rel.parent.as_posix()
        rel_path = posixpath.relpath(asset_path, start=md_dir if md_dir not in {"", "."} else ".")
        return {
            "ok": True,
            "site": site,
            "path": rel_path,
            "filename": filename,
            "original_name": original_name,
            "kind": kind,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Upload failed: {exc}")


@router.get("/folders")
async def list_folders(
    site: str = Query(..., description="schaden|betrieb|vertrieb|allgemein|buchhaltung|novas|datenschutz|wto|it-faq|testumgebung"),
    user: CurrentUser = Depends(require_role("editor")),
):
    docs_dir, drafts_dir, _ = _resolve_site(site)
    return {"ok": True, "site": site, "folders": _all_markdown_folders(docs_dir, drafts_dir)}


@router.post("/create")
async def create_item(
    site: str = Form(...),
    parent: str = Form(""),
    kind: str = Form(...),
    name: str = Form(...),
    user: CurrentUser = Depends(require_role("editor")),
):
    kind_normalized = (kind or "").strip().lower()
    if kind_normalized not in {"file", "folder"}:
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    parent_rel = _safe_rel_path(parent)
    result = create_draft_item(REPO_ROOT, site, parent_rel, kind_normalized, name)
    rel_path = result.get("open_file") or parent_rel.as_posix()
    folder_path = Path(rel_path).parent.as_posix() if kind_normalized == "folder" else rel_path
    append_log(
        rel_path if kind_normalized == "file" else None,
        user,
        "draft_saved",
        {
            "area": site,
            "storage": "local",
            "operation": "folder_created" if kind_normalized == "folder" else "file_created",
            "kind": kind_normalized,
            "path": folder_path,
        },
    )
    payload = {"ok": True, "site": site}
    if kind_normalized == "folder":
        payload["folder"] = folder_path
        payload["file"] = rel_path
    else:
        payload["file"] = rel_path
    return payload


@router.post("/move")
async def move_item(
    site: str = Form(...),
    source: str = Form(...),
    target_parent: str = Form(""),
    kind: str = Form(...),
    new_name: str = Form(""),
    user: CurrentUser = Depends(require_role("editor")),
):
    kind_normalized = (kind or "").strip().lower()
    if kind_normalized not in {"file", "folder"}:
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    source_rel = _move_source_rel(site, source, kind_normalized)
    source_rel = Path("." if str(source_rel) in {"", "."} else source_rel)
    target_parent_rel = _safe_rel_path(target_parent)
    result = move_draft_item(
        REPO_ROOT,
        site,
        source_rel,
        kind_normalized,
        target_parent_rel,
        (new_name or "").strip() or None,
    )
    source_origin = result.get("source_origin") or "draft"
    rel_target = result.get("open_file") or ""
    append_log(
        rel_target if kind_normalized == "file" else None,
        user,
        "draft_saved",
        {
            "area": site,
            "storage": "local",
            "operation": "renamed" if new_name.strip() else "moved",
            "kind": kind_normalized,
            "from": source_rel.as_posix() if str(source_rel) != "." else "",
            "to": rel_target if kind_normalized == "file" else Path(rel_target).parent.as_posix(),
            "source_origin": source_origin,
        },
    )

    payload = {"ok": True, "site": site}
    if kind_normalized == "file":
        payload["file"] = rel_target
    else:
        payload["folder"] = Path(rel_target).parent.as_posix()
        payload["file"] = rel_target
    return payload


@router.get("/delete_preview")
async def delete_preview(
    site: str = Query(...),
    target: str = Query(...),
    kind: str = Query(...),
    user: CurrentUser = Depends(require_role("editor")),
):
    docs_dir, drafts_dir, _ = _resolve_site(site)
    kind_normalized = (kind or "").strip().lower()
    if kind_normalized not in {"file", "folder"}:
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    target_rel = _safe_rel(target) if kind_normalized == "file" else _safe_rel_path(target)
    target_rel = Path("." if str(target_rel) in {"", "."} else target_rel)
    target_path, source_origin = _draft_or_live_path(docs_dir=docs_dir, drafts_dir=drafts_dir, rel=target_rel)

    if kind_normalized == "file":
        return {"ok": True, "site": site, "kind": "file", "path": target_rel.as_posix(), "files": [], "source_origin": source_origin}

    descendants = _list_descendant_files(target_path)
    return {"ok": True, "site": site, "kind": "folder", "path": target_rel.as_posix(), "files": descendants, "source_origin": source_origin}


@router.post("/delete")
async def delete_item(
    site: str = Form(...),
    target: str = Form(...),
    kind: str = Form(...),
    user: CurrentUser = Depends(require_role("editor")),
):
    docs_dir, drafts_dir, _ = _resolve_site(site)
    kind_normalized = (kind or "").strip().lower()
    if kind_normalized not in {"file", "folder"}:
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    target_rel = _safe_rel(target) if kind_normalized == "file" else _safe_rel_path(target)
    target_rel = Path("." if str(target_rel) in {"", "."} else target_rel)
    target_path, source_origin = _draft_or_live_path(docs_dir=docs_dir, drafts_dir=drafts_dir, rel=target_rel)
    if kind_normalized == "file" and not target_path.is_file():
        raise HTTPException(status_code=400, detail="Datei nicht gefunden")
    if kind_normalized == "folder" and not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Ordner nicht gefunden")

    result = None
    if source_origin == "draft":
        result = delete_draft_item(REPO_ROOT, site, target_rel, kind_normalized)
    log_file = target_rel.as_posix() if kind_normalized == "file" else None

    append_log(
        log_file,
        user,
        "draft_saved",
        {
            "area": site,
            "storage": "local",
            "operation": "deleted",
            "kind": kind_normalized,
            "path": target_rel.as_posix() if str(target_rel) != "." else "",
            "deleted_kind": (result or {}).get("deleted_kind", kind_normalized),
            "source_origin": source_origin,
        },
    )
    return {"ok": True, "site": site, "source_origin": source_origin}
