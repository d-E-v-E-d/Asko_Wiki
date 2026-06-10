from __future__ import annotations

from pathlib import Path
from typing import Any

import shutil
import yaml
from fastapi import HTTPException
from app.site_registry import site_folder


def safe_rel_dir(path: str) -> Path:
    p = (path or "").strip().replace("\\", "/").strip("/")
    if not p:
        return Path(".")
    rel = Path(p)
    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Ungueltiger Ordnerpfad")
    return rel


def normalize_create_name(name: str, kind: str) -> str:
    raw = (name or "").strip().replace("\\", "/").strip("/")
    if not raw:
        raise HTTPException(status_code=400, detail="Name fehlt")
    if "/" in raw or "\\" in raw or raw in {".", ".."}:
        raise HTTPException(status_code=400, detail="Ungueltiger Name")

    if kind == "file":
        if not raw.lower().endswith(".md"):
            raw += ".md"
        if raw.startswith(".") or raw.lower() == ".pages":
            raise HTTPException(status_code=400, detail="Ungueltiger Dateiname")
        return raw

    if kind == "folder":
        if raw.startswith("."):
            raise HTTPException(status_code=400, detail="Ungueltiger Ordnername")
        return raw

    raise HTTPException(status_code=400, detail="Ungueltiger Typ")


def title_from_name(name: str) -> str:
    base = Path(name).stem
    return base.replace("_", " ").replace("-", " ").strip() or "Neuer Eintrag"


def _repo_rel(repo_root: Path, path: Path) -> str:
    return path.resolve().relative_to(repo_root.resolve()).as_posix()


def _site_roots(repo_root: Path, site: str) -> tuple[Path, Path]:
    site_root = repo_root / "sites" / site_folder(site)
    return site_root / "docs", site_root / "docs_draft"


def _load_pages_data(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    arrange = data.get("arrange")
    if not isinstance(arrange, list):
        data["arrange"] = []
    return data


def _write_pages_data(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")


def _folder_paths(repo_root: Path, site: str, rel_dir: Path) -> tuple[Path, Path]:
    docs_root, draft_root = _site_roots(repo_root, site)
    rel_dir = Path(".") if str(rel_dir) in {"", "."} else rel_dir
    return docs_root / rel_dir, draft_root / rel_dir


def _ensure_parent_exists(repo_root: Path, site: str, rel_dir: Path) -> tuple[Path, Path]:
    live_dir, draft_dir = _folder_paths(repo_root, site, rel_dir)
    if not live_dir.exists() and not draft_dir.exists():
        raise HTTPException(status_code=404, detail="Zielordner nicht gefunden")
    draft_dir.mkdir(parents=True, exist_ok=True)
    return live_dir, draft_dir


def ensure_draft_pages_entry(repo_root: Path, site: str, rel_dir: Path, entry_name: str) -> str:
    live_dir, draft_dir = _ensure_parent_exists(repo_root, site, rel_dir)

    draft_pages = draft_dir / ".pages"
    live_pages = live_dir / ".pages"

    data = _load_pages_data(draft_pages if draft_pages.exists() else live_pages)
    arrange = data.get("arrange") or []

    if "index.md" not in arrange and ((draft_dir / "index.md").exists() or (live_dir / "index.md").exists()):
        arrange.insert(0, "index.md")
    if entry_name not in arrange:
        arrange.append(entry_name)

    data["arrange"] = arrange
    _write_pages_data(draft_pages, data)
    return _repo_rel(repo_root, draft_pages)


def create_draft_item(repo_root: Path, site: str, parent_dir: Path, kind: str, name: str) -> dict[str, Any]:
    docs_root, draft_root = _site_roots(repo_root, site)
    parent_dir = Path(".") if str(parent_dir) in {"", "."} else parent_dir
    parent_live, parent_draft = _ensure_parent_exists(repo_root, site, parent_dir)

    normalized = normalize_create_name(name, kind)
    add_paths: list[str] = []

    if kind == "file":
        rel_file = parent_dir / normalized
        live_file = docs_root / rel_file
        draft_file = draft_root / rel_file
        if live_file.exists() or draft_file.exists():
            raise HTTPException(status_code=409, detail="Datei existiert bereits")

        draft_file.parent.mkdir(parents=True, exist_ok=True)
        draft_file.write_text(f"# {title_from_name(normalized)}\n", encoding="utf-8")
        add_paths.append(_repo_rel(repo_root, draft_file))
        add_paths.append(ensure_draft_pages_entry(repo_root, site, parent_dir, draft_file.name))
        return {
            "created_kind": "file",
            "open_file": rel_file.as_posix(),
            "add_paths": list(dict.fromkeys(add_paths)),
        }

    folder_rel = parent_dir / normalized
    live_folder = docs_root / folder_rel
    draft_folder = draft_root / folder_rel
    if live_folder.exists() or draft_folder.exists():
        raise HTTPException(status_code=409, detail="Ordner existiert bereits")

    draft_folder.mkdir(parents=True, exist_ok=True)
    index_path = draft_folder / "index.md"
    index_path.write_text(
        f"# {title_from_name(normalized)}\n\n## Inhaltsverzeichnis\n\n<div id=\"section-toc\"></div>\n",
        encoding="utf-8",
    )
    folder_pages = draft_folder / ".pages"
    _write_pages_data(folder_pages, {"arrange": ["index.md"]})

    add_paths.append(_repo_rel(repo_root, index_path))
    add_paths.append(_repo_rel(repo_root, folder_pages))
    add_paths.append(ensure_draft_pages_entry(repo_root, site, parent_dir, normalized))

    return {
        "created_kind": "folder",
        "open_file": (folder_rel / "index.md").as_posix(),
        "add_paths": list(dict.fromkeys(add_paths)),
    }


def _pages_target_for_item(rel_md: Path) -> tuple[Path, str, bool]:
    if rel_md.name == "index.md" and rel_md.parent != Path("."):
        return rel_md.parent.parent, rel_md.parent.name, True
    return rel_md.parent, rel_md.name, False


def _merge_entry_from_draft_order(live_arrange: list[str], draft_arrange: list[str], entry_name: str) -> list[str]:
    if entry_name in live_arrange:
        return live_arrange
    if entry_name not in draft_arrange:
        return live_arrange + [entry_name]

    entry_idx = draft_arrange.index(entry_name)

    for next_name in draft_arrange[entry_idx + 1:]:
        if next_name in live_arrange:
            insert_at = live_arrange.index(next_name)
            return live_arrange[:insert_at] + [entry_name] + live_arrange[insert_at:]

    for prev_name in reversed(draft_arrange[:entry_idx]):
        if prev_name in live_arrange:
            insert_at = live_arrange.index(prev_name) + 1
            return live_arrange[:insert_at] + [entry_name] + live_arrange[insert_at:]

    return live_arrange + [entry_name]


def sync_live_pages_for_item(repo_root: Path, site: str, rel_md: Path) -> list[str]:
    docs_root, draft_root = _site_roots(repo_root, site)
    parent_rel, entry_name, is_folder_index = _pages_target_for_item(rel_md)

    extra_paths: list[str] = []
    if str(parent_rel) not in {"", "."} or entry_name != "index.md":
        live_parent_dir = docs_root / parent_rel
        draft_parent_dir = draft_root / parent_rel
        live_parent_dir.mkdir(parents=True, exist_ok=True)

        live_pages = live_parent_dir / ".pages"
        draft_pages = draft_parent_dir / ".pages"

        live_data = _load_pages_data(live_pages)
        draft_data = _load_pages_data(draft_pages if draft_pages.exists() else live_pages)

        live_arrange = list(live_data.get("arrange") or [])
        draft_arrange = list(draft_data.get("arrange") or [])
        merged = _merge_entry_from_draft_order(live_arrange, draft_arrange, entry_name)

        if "index.md" not in merged and (live_parent_dir / "index.md").exists():
            merged.insert(0, "index.md")

        if merged != live_arrange:
            live_data["arrange"] = merged
            _write_pages_data(live_pages, live_data)
            extra_paths.append(_repo_rel(repo_root, live_pages))

    if is_folder_index:
        live_folder = docs_root / rel_md.parent
        draft_folder = draft_root / rel_md.parent
        live_pages = live_folder / ".pages"
        draft_pages = draft_folder / ".pages"
        if draft_pages.exists() and not live_pages.exists():
            live_folder.mkdir(parents=True, exist_ok=True)
            live_pages.write_text(draft_pages.read_text(encoding="utf-8"), encoding="utf-8")
            extra_paths.append(_repo_rel(repo_root, live_pages))

    return list(dict.fromkeys(extra_paths))


def cleanup_draft_pages_for_rejected_item(repo_root: Path, site: str, rel_md: Path) -> list[str]:
    docs_root, draft_root = _site_roots(repo_root, site)
    parent_rel, entry_name, is_folder_index = _pages_target_for_item(rel_md)

    extra_paths: list[str] = []

    live_item = docs_root / rel_md
    if live_item.exists():
        return extra_paths

    draft_parent_dir = draft_root / parent_rel
    draft_pages = draft_parent_dir / ".pages"
    if draft_pages.exists():
        data = _load_pages_data(draft_pages)
        arrange = [x for x in (data.get("arrange") or []) if x != entry_name]
        data["arrange"] = arrange
        _write_pages_data(draft_pages, data)
        extra_paths.append(_repo_rel(repo_root, draft_pages))

    if is_folder_index:
        draft_folder = draft_root / rel_md.parent
        draft_folder_pages = draft_folder / ".pages"
        if draft_folder_pages.exists():
            draft_folder_pages.unlink()
            extra_paths.append(_repo_rel(repo_root, draft_folder_pages))
        if draft_folder.exists():
            try:
                draft_folder.rmdir()
            except OSError:
                pass

    return list(dict.fromkeys(extra_paths))


def list_folder_paths(repo_root: Path, site: str) -> list[str]:
    docs_root, draft_root = _site_roots(repo_root, site)
    folders: set[str] = {""}

    for root in (docs_root, draft_root):
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_dir():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in {"assets", "assets/images"} or rel.startswith("assets/"):
                continue
            folders.add("" if rel == "." else rel)

    return sorted(folders, key=lambda x: (x.count("/"), x.lower()))


def _is_orderable_child(path: Path) -> bool:
    if path.name.startswith("."):
        return False
    if path.is_file():
        return path.suffix.lower() == ".md"
    if path.is_dir():
        return path.name not in {"assets", "styles", "print", "exports", "site", "review", "__pycache__"}
    return False


def _order_child_type(path: Path) -> str:
    return "folder" if path.is_dir() else "file"


def list_pages_order(repo_root: Path, site: str, rel_dir: Path) -> dict[str, Any]:
    docs_root, draft_root = _site_roots(repo_root, site)
    rel_dir = Path(".") if str(rel_dir) in {"", "."} else rel_dir
    live_dir = docs_root / rel_dir
    draft_dir = draft_root / rel_dir

    if not live_dir.exists() and not draft_dir.exists():
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")

    live_pages = live_dir / ".pages"
    draft_pages = draft_dir / ".pages"
    pages_data = _load_pages_data(draft_pages if draft_pages.exists() else live_pages)
    arrange = [str(item).strip() for item in (pages_data.get("arrange") or []) if str(item).strip()]

    children: dict[str, dict[str, Any]] = {}
    for source, folder in (("live", live_dir), ("draft", draft_dir)):
        if not folder.exists():
            continue
        for child in folder.iterdir():
            if not _is_orderable_child(child):
                continue
            current = children.get(child.name)
            if current and current.get("source") == "draft":
                continue
            children[child.name] = {
                "name": child.name,
                "type": _order_child_type(child),
                "source": source,
                "locked": child.name.lower() == "index.md",
            }

    ordered_names: list[str] = []
    if "index.md" in children:
        ordered_names.append("index.md")
    for name in arrange:
        if name in children and name not in ordered_names:
            ordered_names.append(name)
    for name in sorted(children, key=lambda value: (0 if value.lower() == "index.md" else 1, value.lower())):
        if name not in ordered_names:
            ordered_names.append(name)

    return {
        "folder": "" if str(rel_dir) in {"", "."} else rel_dir.as_posix(),
        "items": [children[name] for name in ordered_names if name in children],
        "arrange": ordered_names,
    }


def save_pages_order(repo_root: Path, site: str, rel_dir: Path, order: list[str]) -> list[str]:
    docs_root, draft_root = _site_roots(repo_root, site)
    rel_dir = Path(".") if str(rel_dir) in {"", "."} else rel_dir
    live_dir = docs_root / rel_dir
    draft_dir = draft_root / rel_dir

    current = list_pages_order(repo_root, site, rel_dir)
    existing = [str(item["name"]) for item in current["items"]]
    existing_set = set(existing)
    requested = [str(name).strip() for name in order if str(name).strip()]

    if set(requested) != existing_set:
        raise HTTPException(status_code=400, detail="Sortierung passt nicht zu den vorhandenen Eintraegen")

    arranged: list[str] = []
    if "index.md" in existing_set:
        arranged.append("index.md")
    for name in requested:
        if name == "index.md" or name in arranged:
            continue
        arranged.append(name)

    touched: list[str] = []
    targets: list[Path] = []
    if live_dir.exists():
        targets.append(live_dir / ".pages")
    if draft_dir.exists() or (draft_dir / ".pages").exists():
        targets.append(draft_dir / ".pages")
    if not targets:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden")

    for pages_path in targets:
        data = _load_pages_data(pages_path)
        if data.get("arrange") == arranged:
            continue
        data["arrange"] = arranged
        _write_pages_data(pages_path, data)
        touched.append(_repo_rel(repo_root, pages_path))

    return list(dict.fromkeys(touched))


def _remove_entry_from_pages(path: Path, entry_name: str) -> bool:
    if not path.exists():
        return False
    data = _load_pages_data(path)
    arrange = list(data.get("arrange") or [])
    new_arrange = [x for x in arrange if x != entry_name]
    if new_arrange == arrange:
        return False
    data["arrange"] = new_arrange
    _write_pages_data(path, data)
    return True


def _remove_entry_for_rel(repo_root: Path, site: str, rel_path: Path, prefer_draft: bool = True) -> list[str]:
    docs_root, draft_root = _site_roots(repo_root, site)
    parent_rel, entry_name, _ = _pages_target_for_item(rel_path)
    touched: list[str] = []

    draft_pages = draft_root / parent_rel / ".pages"
    live_pages = docs_root / parent_rel / ".pages"

    if prefer_draft and _remove_entry_from_pages(draft_pages, entry_name):
        touched.append(_repo_rel(repo_root, draft_pages))
    elif _remove_entry_from_pages(live_pages, entry_name):
        touched.append(_repo_rel(repo_root, live_pages))
    elif _remove_entry_from_pages(draft_pages, entry_name):
        touched.append(_repo_rel(repo_root, draft_pages))

    return touched


def move_draft_item(
    repo_root: Path,
    site: str,
    source_rel: Path,
    kind: str,
    target_parent: Path,
    new_name: str | None = None,
) -> dict[str, Any]:
    docs_root, draft_root = _site_roots(repo_root, site)

    target_parent = Path(".") if str(target_parent) in {"", "."} else target_parent
    _ensure_parent_exists(repo_root, site, target_parent)

    add_paths: list[str] = []
    normalized_kind = (kind or "").strip().lower()

    if normalized_kind == "file":
        src_rel = source_rel
        src_draft = draft_root / src_rel
        src_live = docs_root / src_rel
        source_origin = "draft" if src_draft.exists() else "live" if src_live.exists() else ""
        if not source_origin:
            raise HTTPException(status_code=404, detail="Datei nicht gefunden (weder Live noch Draft)")

        target_name = normalize_create_name(new_name or src_rel.name, "file")
        dest_rel = target_parent / target_name
        dest_draft = draft_root / dest_rel
        dest_live = docs_root / dest_rel

        if src_rel == dest_rel:
            raise HTTPException(status_code=400, detail="Datei ist bereits an diesem Ort")
        if dest_draft.exists() or dest_live.exists():
            raise HTTPException(status_code=409, detail="Zieldatei existiert bereits")

        dest_draft.parent.mkdir(parents=True, exist_ok=True)
        if source_origin == "draft":
            src_draft.replace(dest_draft)
            add_paths.append(_repo_rel(repo_root, src_draft))
        else:
            shutil.copy2(src_live, dest_draft)
        add_paths.append(_repo_rel(repo_root, dest_draft))

        if source_origin == "draft":
            add_paths.extend(_remove_entry_for_rel(repo_root, site, src_rel, prefer_draft=not src_live.exists()))
        add_paths.append(ensure_draft_pages_entry(repo_root, site, target_parent, dest_draft.name))

        return {
            "moved_kind": "file",
            "open_file": dest_rel.as_posix(),
            "source_origin": source_origin,
            "add_paths": list(dict.fromkeys(add_paths)),
        }

    if normalized_kind != "folder":
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    src_folder_rel = Path(".") if str(source_rel) in {"", "."} else source_rel
    if src_folder_rel == Path("."):
        raise HTTPException(status_code=400, detail="Wurzelordner kann nicht verschoben werden")

    src_draft = draft_root / src_folder_rel
    src_live = docs_root / src_folder_rel
    source_origin = "draft" if src_draft.exists() else "live" if src_live.exists() else ""
    if not source_origin:
        raise HTTPException(status_code=404, detail="Ordner nicht gefunden (weder Live noch Draft)")

    target_name = normalize_create_name(new_name or src_folder_rel.name, "folder")
    dest_rel = target_parent / target_name
    dest_draft = draft_root / dest_rel
    dest_live = docs_root / dest_rel

    if src_folder_rel == dest_rel:
        raise HTTPException(status_code=400, detail="Ordner ist bereits an diesem Ort")
    if src_folder_rel in target_parent.parents:
        raise HTTPException(status_code=400, detail="Ordner kann nicht in sich selbst verschoben werden")
    if dest_draft.exists() or dest_live.exists():
        raise HTTPException(status_code=409, detail="Zielordner existiert bereits")

    dest_draft.parent.mkdir(parents=True, exist_ok=True)
    if source_origin == "draft":
        src_draft.replace(dest_draft)
        add_paths.append(_repo_rel(repo_root, src_draft))
    else:
        shutil.copytree(src_live, dest_draft)
    add_paths.append(_repo_rel(repo_root, dest_draft))

    if source_origin == "draft":
        add_paths.extend(_remove_entry_for_rel(repo_root, site, src_folder_rel / "index.md", prefer_draft=True))
    add_paths.append(ensure_draft_pages_entry(repo_root, site, target_parent, dest_draft.name))

    return {
        "moved_kind": "folder",
        "open_file": (dest_rel / "index.md").as_posix(),
        "source_origin": source_origin,
        "add_paths": list(dict.fromkeys(add_paths)),
    }


def delete_draft_item(repo_root: Path, site: str, target_rel: Path, kind: str) -> dict[str, Any]:
    docs_root, draft_root = _site_roots(repo_root, site)
    add_paths: list[str] = []

    if kind == "file":
        rel = target_rel
        draft_file = draft_root / rel
        live_file = docs_root / rel
        if not draft_file.exists():
            raise HTTPException(status_code=404, detail="Draft-Datei nicht gefunden")

        parent_rel, entry_name, _ = _pages_target_for_item(rel)
        parent_draft_pages = draft_root / parent_rel / ".pages"
        parent_live_pages = docs_root / parent_rel / ".pages"

        draft_file.unlink()
        add_paths.append(_repo_rel(repo_root, draft_file))

        if _remove_entry_from_pages(parent_draft_pages, entry_name):
            add_paths.append(_repo_rel(repo_root, parent_draft_pages))
        elif not live_file.exists() and _remove_entry_from_pages(parent_live_pages, entry_name):
            add_paths.append(_repo_rel(repo_root, parent_live_pages))

        return {"deleted_kind": "file", "add_paths": list(dict.fromkeys(add_paths))}

    if kind != "folder":
        raise HTTPException(status_code=400, detail="Ungueltiger Typ")

    folder_rel = Path(".") if str(target_rel) in {"", "."} else target_rel
    if folder_rel == Path("."):
        raise HTTPException(status_code=400, detail="Wurzelordner kann nicht geloescht werden")

    draft_folder = draft_root / folder_rel
    live_folder = docs_root / folder_rel

    if not draft_folder.exists():
        raise HTTPException(status_code=404, detail="Draft-Ordner nicht gefunden")
    if live_folder.exists():
        raise HTTPException(status_code=400, detail="Ordner existiert bereits live und kann hier nicht geloescht werden")

    for child in sorted(draft_folder.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if child.is_file():
            child.unlink()
            add_paths.append(_repo_rel(repo_root, child))
        elif child.is_dir():
            try:
                child.rmdir()
            except OSError:
                pass

    try:
        draft_folder.rmdir()
    except OSError:
        raise HTTPException(status_code=400, detail="Ordner konnte nicht geloescht werden")

    add_paths.append(_repo_rel(repo_root, draft_folder))

    parent_rel = folder_rel.parent
    entry_name = folder_rel.name
    parent_draft_pages = draft_root / parent_rel / ".pages"
    parent_live_pages = docs_root / parent_rel / ".pages"

    if _remove_entry_from_pages(parent_draft_pages, entry_name):
        add_paths.append(_repo_rel(repo_root, parent_draft_pages))
    elif _remove_entry_from_pages(parent_live_pages, entry_name):
        add_paths.append(_repo_rel(repo_root, parent_live_pages))

    return {"deleted_kind": "folder", "add_paths": list(dict.fromkeys(add_paths))}
