# app/services/build_service.py
from __future__ import annotations

from pathlib import Path
import datetime
import os
import re
import shutil
import tempfile
import subprocess
from typing import Tuple, Optional, Dict, Any, List

from bs4 import BeautifulSoup
import yaml

from app.config import config
from app.services.version_service import set_version, get_version
from app.site_registry import COUNTRY_KEYS, SITE_KEYS, site_folder, site_route, normalize_site

# ---------- Repo Layout (multi-site) ----------
def _find_repo_root(start: Path) -> Path:
    """
    Sucht nach dem Ordner, der sowohl 'sites' als auch 'portal' enthält.
    Damit ist es egal, ob build_service.py unter app/services oder app/app/services liegt.
    """
    start = start.resolve()
    for p in [start.parent] + list(start.parents):
        if (p / "sites").exists() and (p / "portal").exists():
            return p
    # Fallback: falls portal noch nicht existiert, zumindest sites finden
    for p in [start.parent] + list(start.parents):
        if (p / "sites").exists():
            return p
    raise RuntimeError(f"Repo root nicht gefunden ab: {start}")


def _pick_mkdocs_cfg(folder: Path) -> Path:
    """Unterstützt mkdocs.yml und mkdocs.yaml."""
    yml = folder / "mkdocs.yml"
    yaml = folder / "mkdocs.yaml"
    if yml.exists():
        return yml
    if yaml.exists():
        return yaml
    return yml  # für klare Fehlermeldung


# ---------- Output / Paths ----------
def _configured_runtime_path(value: str, fallback_name: str) -> Path:
    """
    Lokale Windows-Tests verwenden APP_ROOT aus tools/run_local.ps1, während config.json
    serverseitige /srv/... Pfade enthält. In diesem Fall auf APP_ROOT/<fallback> mappen.
    """
    raw = str(value or fallback_name)
    app_root = os.environ.get("APP_ROOT")
    normalized = raw.replace("\\", "/")
    if app_root and normalized.startswith("/srv/arbeitsanweisung/app/"):
        suffix = normalized[len("/srv/arbeitsanweisung/app/"):].strip("/")
        return Path(app_root) / (suffix or fallback_name)
    return Path(raw)


SITE_DIR = _configured_runtime_path(config.get("paths", "site", "site"), "site")
WWWROOT = _configured_runtime_path(
    config.get("paths", "wwwroot_arbeitsanweisung", config.get("paths", "wwwroot", "wwwroot_arbeitsanweisung")),
    "wwwroot_arbeitsanweisung",
)
VERSION_FILE = Path(config.get("versioning", "version_file", "version.json"))

# Repo Root robust bestimmen
REPO_ROOT = Path(os.environ["REPO_ROOT"]).resolve() if os.environ.get("REPO_ROOT") else _find_repo_root(Path(__file__))

PORTAL_MKDOCS = _pick_mkdocs_cfg(REPO_ROOT / "portal")
SITES_DIR = REPO_ROOT / "sites"
SHARED_DIR = REPO_ROOT / "shared"

ALLOWED_SITES = list(SITE_KEYS)
# ---------- Git ----------
GIT_ENABLED = bool(config.get("git", "enabled", False))
GIT_REMOTE = config.get("git", "remote", "origin")
GIT_BRANCH = config.get("git", "branch", "main")
CONTENT_GIT_SYNC_ENABLED = str(
    config.get("git", "content_sync_enabled", os.environ.get("ASKO_ALLOW_CONTENT_GIT_SYNC", "0"))
).strip().lower() in {"1", "true", "yes", "on"}
GIT_STATUS_IGNORE_PATHS = [
    "config.json",
    "config.local.json",
    "users.json",
    "review",
    "site",
    "wwwroot_arbeitsanweisung",
]


def _is_content_git_path(path: str) -> bool:
    clean = (path or "").replace("\\", "/").strip("/")
    return clean == "sites" or clean.startswith("sites/") or clean == "review" or clean.startswith("review/")


def _content_sync_disabled_message(paths: list[str] | None = None) -> str:
    suffix = ""
    if paths:
        suffix = "\nBlockierte Pfade:\n" + "\n".join(f"- {p}" for p in paths)
    return "Content-Git-Sync ist deaktiviert: sites/review werden nicht zu GitHub synchronisiert." + suffix


def _run(cmd: list[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> Tuple[bool, str]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            env=env or os.environ.copy(),
        )
    except FileNotFoundError as exc:
        return False, f"Befehl nicht gefunden: {cmd[0]} ({exc})"
    out = (proc.stdout or "") + ("\n" + (proc.stderr or "") if proc.stderr else "")
    return proc.returncode == 0, out.strip()


def _refresh_build_metadata(version: Optional[str] = None) -> Dict[str, str]:
    current = get_version(site="portal")
    target_version = (version or current.get("version") or "").strip()
    if not target_version:
        target_version = datetime.date.today().isoformat()
    return set_version(target_version, site="portal", mirror_to_sites=True)


def git_pull_merge() -> Tuple[bool, str]:
    _run(["git", "config", "pull.rebase", "false"], cwd=REPO_ROOT)
    return _run(["git", "pull", "--no-rebase", GIT_REMOTE, GIT_BRANCH], cwd=REPO_ROOT)


def _git_status_exclude_args(paths: list[str]) -> list[str]:
    return [f":(exclude){p}" for p in paths]


def _git_add_paths_for_site(site: str) -> List[str]:
    """
    Source-of-truth, die commit/pushen darf:
      - shared/ (assets, overrides)
      - portal/ (docs + mkdocs.yml)
      - sites/<site>/ (docs, docs_draft, mkdocs.yml)
      - version file (optional)
    """
    paths: List[str] = []

    if (REPO_ROOT / "shared").exists():
        paths.append("shared")

    if (REPO_ROOT / "portal").exists():
        paths.append("portal/docs")
        paths.append("portal/mkdocs.yml")

    if site == "all":
        for s in ALLOWED_SITES:
            base = f"sites/{site_folder(s)}"
            if (REPO_ROOT / base).exists():
                if (REPO_ROOT / base / "docs").exists():
                    paths.append(f"{base}/docs")
                if (REPO_ROOT / base / "docs_draft").exists():
                    paths.append(f"{base}/docs_draft")
                if (REPO_ROOT / base / "mkdocs.yml").exists():
                    paths.append(f"{base}/mkdocs.yml")
    else:
        base = f"sites/{site_folder(site)}"
        if (REPO_ROOT / base).exists():
            if (REPO_ROOT / base / "docs").exists():
                paths.append(f"{base}/docs")
            if (REPO_ROOT / base / "docs_draft").exists():
                paths.append(f"{base}/docs_draft")
            if (REPO_ROOT / base / "mkdocs.yml").exists():
                paths.append(f"{base}/mkdocs.yml")

    if VERSION_FILE.exists():
        try:
            paths.append(str(VERSION_FILE.relative_to(REPO_ROOT)))
        except Exception:
            pass

    out: List[str] = []
    seen = set()
    for p in paths:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out


def git_commit_and_push_docs(message: str, site: str = "all") -> Tuple[bool, str]:
    if not CONTENT_GIT_SYNC_ENABLED:
        return True, _content_sync_disabled_message(_git_add_paths_for_site(site))

    ok, out = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO_ROOT)
    if not ok:
        return False, f"Kein Git-Repo: {REPO_ROOT}\n{out}"

    add_paths = _git_add_paths_for_site(site)

    ok_add, out_add = _run(["git", "add", "--"] + add_paths, cwd=REPO_ROOT)
    if not ok_add:
        return False, f"git add fehlgeschlagen\n{out_add}"

    ok_diff, out_diff = _run(["git", "diff", "--cached", "--name-only"], cwd=REPO_ROOT)
    if not ok_diff:
        return False, f"git diff --cached fehlgeschlagen\n{out_diff}"
    if out_diff.strip() == "":
        return True, "Nichts zu committen (Docs unverändert)."

    ok_commit, out_commit = _run(["git", "commit", "-m", message], cwd=REPO_ROOT)
    if not ok_commit:
        return False, f"git commit fehlgeschlagen\n{out_commit}"

    ok_push, out_push = _run(["git", "push", GIT_REMOTE, GIT_BRANCH], cwd=REPO_ROOT)
    if not ok_push:
        return False, f"git push fehlgeschlagen\n{out_push}"

    return True, (out_add + "\n" + out_commit + "\n" + out_push).strip()


def _mkdocs_build_one(cfg: Path, out_dir: Path, enable_pdf: bool) -> Tuple[bool, str]:
    if not cfg.exists():
        return False, f"mkdocs config fehlt: {cfg}"

    env = os.environ.copy()
    if enable_pdf:
        env["ENABLE_PDF_EXPORT"] = "1"
    else:
        env.pop("ENABLE_PDF_EXPORT", None)

    out_dir.mkdir(parents=True, exist_ok=True)

    # clean nur in out_dir (wichtig: out_dir darf NICHT dein gesamter SITE_DIR sein!)
    cmd = ["mkdocs", "build", "-c", "-f", str(cfg), "-d", str(out_dir)]
    return _run(cmd, cwd=REPO_ROOT, env=env)


def _copy_tree_contents(source: Path, target: Path) -> None:
    if not source.exists():
        return
    target.mkdir(parents=True, exist_ok=True)
    for item in source.iterdir():
        destination = target / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def _sync_shared_mkdocs_assets() -> str:
    """
    Synchronisiert technische MkDocs-Dateien aus shared/ in alle lokalen Bereiche.
    Inhalte unter docs/ und docs_draft/ bleiben erhalten; es werden nur gemeinsame
    Assets/Overrides ergänzt oder aktualisiert.
    """
    if not SHARED_DIR.exists():
        return "shared/ nicht vorhanden"

    shared_assets = SHARED_DIR / "assets"
    shared_overrides = SHARED_DIR / "overrides"
    synced = 0

    for site in ALLOWED_SITES:
        site_root = SITES_DIR / site_folder(site)
        if not site_root.exists():
            continue
        if shared_overrides.exists():
            _copy_tree_contents(shared_overrides, site_root / "overrides")
            synced += 1
        if shared_assets.exists():
            for docs_name in ("docs", "docs_draft"):
                docs_root = site_root / docs_name
                if docs_root.exists():
                    _copy_tree_contents(shared_assets, docs_root / "assets")
                    synced += 1

    return f"shared sync OK ({synced} Ziele)"



def _site_has_markdown(site: str) -> bool:
    docs_root = SITES_DIR / site_folder(site) / "docs"
    return docs_root.exists() and any(docs_root.rglob("*.md"))

def _merge_portal_into_site_root(portal_out: Path) -> Tuple[bool, str]:
    """
    Kopiert Portal-Output nach SITE_DIR (Root), ohne die Bereich-Ordner (schaden/, betrieb/, ...) zu löschen.
    Benutzt rsync, damit veraltete Portal-Dateien entfernt werden (aber EXCLUDES bleiben stehen).
    """
    if not portal_out.exists():
        return False, f"Portal-Output fehlt: {portal_out}"

    # rsync --delete, aber excludes für Bereiche + .portal_tmp selbst
    exclude_args: List[str] = []
    for s in ALLOWED_SITES:
        exclude_args += ["--exclude", f"/{site_route(s)}/"]
    exclude_args += ["--exclude", "/.portal_tmp/"]

    cmd = ["rsync", "-a", "--delete"] + exclude_args + [f"{portal_out}/", f"{SITE_DIR}/"]
    ok, out = _run(cmd, cwd=REPO_ROOT)
    if ok or "Befehl nicht gefunden: rsync" not in out:
        return ok, out

    # Windows/local fallback: mirror portal files while preserving built area folders.
    try:
        SITE_DIR.mkdir(parents=True, exist_ok=True)
        keep_names = set(COUNTRY_KEYS) | {".portal_tmp"}

        for child in SITE_DIR.iterdir():
            if child.name in keep_names:
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        for source in portal_out.iterdir():
            target = SITE_DIR / source.name
            if source.is_dir():
                if target.exists() and source.name in COUNTRY_KEYS:
                    shutil.copytree(source, target, dirs_exist_ok=True)
                else:
                    if target.exists():
                        shutil.rmtree(target)
                    shutil.copytree(source, target)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

        return True, "Portal-Merge OK (lokaler shutil-Fallback, rsync nicht gefunden)."
    except Exception as exc:
        return False, f"Portal-Merge Fallback fehlgeschlagen: {exc}"


def mkdocs_build(site: str = "all", enable_pdf: bool = False) -> Tuple[bool, str]:
    """
    site:
      - "all"    => portal + alle Bereiche
      - "schaden"|"betrieb"|... => nur diesen Bereich + portal refresh
    """
    site = (site or "all").strip().lower()
    if site != "all":
        try:
            site = normalize_site(site)
        except KeyError:
            pass
    if site != "all" and site not in ALLOWED_SITES:
        return False, f"Ungültige Site: {site}"

    logs: List[str] = []

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        logs.append("[shared] " + _sync_shared_mkdocs_assets())
    except Exception as exc:
        return False, f"[shared] FEHLER\n{exc}"

    # 1) Portal in temp bauen (niemals direkt nach SITE_DIR wegen -c!)
    portal_tmp = SITE_DIR / ".portal_tmp"
    ok_p, out_p = _mkdocs_build_one(PORTAL_MKDOCS, portal_tmp, enable_pdf=False)  # portal nie PDF
    logs.append("[portal] " + ("OK" if ok_p else "FEHLER") + "\n" + out_p)
    if not ok_p:
        return False, "\n\n".join(logs)

    ok_m, out_m = _merge_portal_into_site_root(portal_tmp)
    logs.append("[portal-merge] " + ("OK" if ok_m else "FEHLER") + "\n" + out_m)
    if not ok_m:
        return False, "\n\n".join(logs)

    # 2) Bereiche
    if site == "all":
        for s in ALLOWED_SITES:
            if not _site_has_markdown(s):
                logs.append(f"[{s}] SKIP - keine Markdown-Inhalte")
                continue
            cfg = SITES_DIR / site_folder(s) / "mkdocs.yml"
            out_dir = SITE_DIR / site_route(s)
            ok, out = _mkdocs_build_one(cfg, out_dir, enable_pdf=enable_pdf)
            logs.append(f"[{s}] " + ("OK" if ok else "FEHLER") + "\n" + out)
            if not ok:
                return False, "\n\n".join(logs)
        return True, "\n\n".join(logs)

    if not _site_has_markdown(site):
        logs.append(f"[{site}] SKIP - keine Markdown-Inhalte")
        return True, "\n\n".join(logs)

    cfg = SITES_DIR / site_folder(site) / "mkdocs.yml"
    out_dir = SITE_DIR / site_route(site)
    ok_s, out_s = _mkdocs_build_one(cfg, out_dir, enable_pdf=enable_pdf)
    logs.append(f"[{site}] " + ("OK" if ok_s else "FEHLER") + "\n" + out_s)
    return ok_s, "\n\n".join(logs)


def deploy_to_wwwroot() -> Tuple[bool, str]:
    WWWROOT.mkdir(parents=True, exist_ok=True)
    cmd = [
        "rsync",
        "-r",                 # rekursiv
        "--delete",           # Ziel auf Quelle spiegeln
        "--no-perms",
        "--no-owner",
        "--no-group",
        "--omit-dir-times",
        "--no-times",
        f"{SITE_DIR}/",
        f"{WWWROOT}/",
    ]
    return _run(cmd, cwd=REPO_ROOT)


def publish_flow(new_version: Optional[str] = None, site: str = "all") -> Dict[str, Any]:
    """
    Publish = lokale Metadaten aktualisieren + Build + Deploy.
    Content-Git-Sync ist standardmaessig deaktiviert.
    """
    site = (site or "all").strip().lower()
    if site != "all":
        try:
            site = normalize_site(site)
        except KeyError:
            pass
    res: Dict[str, Any] = {"steps": [], "site": site}

    v = _refresh_build_metadata(version=new_version)
    res["version"] = v
    res["steps"].append(f"Version: {v.get('version')} ({v.get('version_date')})")

    if GIT_ENABLED:
        # Bei Versionsupdate werden mkdocs.yml in allen Sites gespiegelt.
        # Deshalb muessen wir dann auch alle Site-Pfade committen, sonst bleibt der Tree dirty.
        git_site_scope = "all" if new_version else site
        ok_git, out_git = git_commit_and_push_docs(
            f"Publish docs {v.get('version')} ({v.get('version_date')})",
            site=git_site_scope
        )
        res["git_output"] = out_git
        res["git_ok"] = ok_git
        if not CONTENT_GIT_SYNC_ENABLED and ok_git:
            res["steps"].append("Git Content-Sync deaktiviert")
        else:
            res["steps"].append("Git push OK" if ok_git else "Git push FEHLER")
        if not ok_git:
            return res
    else:
        res["steps"].append("Git: deaktiviert")

    ok_build, out_build = mkdocs_build(site=site, enable_pdf=False)
    res["build_ok"] = ok_build
    res["build_output"] = out_build
    res["steps"].append("mkdocs build OK" if ok_build else "mkdocs build FEHLER")
    if not ok_build:
        return res

    ok_dep, out_dep = deploy_to_wwwroot()
    res["deploy_ok"] = ok_dep
    res["deploy_output"] = out_dep
    res["steps"].append("Deploy OK" if ok_dep else "Deploy FEHLER")
    return res


def _pdf_export_name() -> str:
    return str(config.get("pdf", "current_filename", "Arbeitsanweisung_AKTUELL.pdf"))


def _pdf_urls_for_site(site: str) -> list[str]:
    pdf_name = _pdf_export_name()

    if site == "all":
        urls: list[str] = []
        for s in ALLOWED_SITES:
            p = SITE_DIR / site_route(s) / "exports" / pdf_name
            if p.exists():
                urls.append(f"/{site_route(s)}/exports/{pdf_name}")
        return urls

    p = SITE_DIR / site_route(site) / "exports" / pdf_name
    if p.exists():
        return [f"/{site_route(site)}/exports/{pdf_name}"]

    return []


def _site_display_name(site: str) -> str:
    cfg = SITES_DIR / site_folder(site) / "mkdocs.yml"
    if cfg.exists():
        try:
            data = yaml.safe_load(cfg.read_text(encoding="utf-8", errors="ignore")) or {}
            if isinstance(data, dict) and data.get("site_name"):
                return str(data.get("site_name"))
        except Exception:
            pass
    return site.capitalize()


def _read_pages_arrange(folder: Path) -> list[str]:
    pages_file = folder / ".pages"
    if not pages_file.exists():
        return []
    try:
        data = yaml.safe_load(pages_file.read_text(encoding="utf-8", errors="ignore")) or {}
    except Exception:
        return []
    arrange = data.get("arrange") if isinstance(data, dict) else []
    if not isinstance(arrange, list):
        return []
    return [str(item).strip() for item in arrange if str(item).strip()]


def _is_content_dir(path: Path) -> bool:
    return path.is_dir() and path.name not in {"assets", "styles", "print", "exports", "site", "review", "__pycache__"}


def _ordered_docs_recursive(folder: Path) -> list[Path]:
    ordered: list[Path] = []
    seen: set[str] = set()

    def add_child(child: Path) -> None:
        key = child.name.lower()
        if key in seen or child.name.startswith("."):
            return
        seen.add(key)
        if child.is_file() and child.suffix.lower() == ".md":
            if child.name.lower() == "index.md":
                return
            ordered.append(child)
        elif _is_content_dir(child):
            ordered.extend(_ordered_docs_recursive(child))

    for name in _read_pages_arrange(folder):
        child = folder / name
        if child.exists():
            add_child(child)

    for child in sorted(folder.iterdir(), key=lambda p: (0 if p.name.lower() == "index.md" else 1, p.name.lower())):
        if child.name == ".pages":
            continue
        add_child(child)

    return ordered


def _html_path_for_doc(docs_root: Path, build_root: Path, doc_path: Path) -> Path:
    rel = doc_path.relative_to(docs_root)
    if rel.name.lower() == "index.md":
        html_rel = rel.with_name("index.html")
    else:
        html_rel = rel.with_suffix("") / "index.html"
    return build_root / html_rel


def _extract_stylesheets(index_html: Path) -> list[str]:
    if not index_html.exists():
        return []
    soup = BeautifulSoup(index_html.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    links: list[str] = []
    seen: set[str] = set()
    blocked_suffixes = (
        "/assets/css/custom.css",
        "/assets/css/pdf-print.css",
        "/assets/css/site-switcher.css",
    )
    for tag in soup.select('link[rel~="stylesheet"]'):
        href = (tag.get("href") or "").strip()
        if not href or href.startswith(("http://", "https://", "data:")):
            continue
        normalized = href.replace("\\", "/")
        if normalized.endswith(blocked_suffixes):
            continue
        css_path = (index_html.parent / href).resolve()
        if not css_path.exists():
            continue
        uri = css_path.as_uri()
        if uri not in seen:
            seen.add(uri)
            links.append(uri)
    return links


def _select_article_node(soup: BeautifulSoup):
    selectors = [
        "article.md-content__inner",
        ".md-content__inner article",
        ".md-content__inner",
        "main article",
        "article",
        "main",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node is not None:
            return node
    return soup.body or soup


def _rewrite_relative_urls(root, page_dir: Path) -> None:
    for tag in root.find_all(src=True):
        src = (tag.get("src") or "").strip()
        if not src or src.startswith(("http://", "https://", "data:", "file:")):
            continue
        tag["src"] = (page_dir / src).resolve().as_uri()

    for tag in root.find_all(href=True):
        href = (tag.get("href") or "").strip()
        if not href or href.startswith(("#", "http://", "https://", "mailto:", "tel:", "data:", "file:")):
            continue
        tag["href"] = (page_dir / href).resolve().as_uri()


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug or "section"


def _render_site_pdf(site: str) -> Tuple[bool, str]:
    try:
        from weasyprint import HTML
    except Exception as exc:
        return False, f"WeasyPrint ist lokal nicht verfuegbar: {exc}"

    site_dir = site_folder(site)
    docs_root = SITES_DIR / site_dir / "docs"
    if not docs_root.exists():
        return False, f"Docs-Verzeichnis fehlt: {docs_root}"

    docs_in_order = _ordered_docs_recursive(docs_root)
    if not docs_in_order:
        return False, f"Keine Markdown-Dateien fuer PDF gefunden: {docs_root}"

    with tempfile.TemporaryDirectory(prefix=f"asko-pdf-{site}-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        build_root = tmp_dir / site
        ok_build, out_build = _mkdocs_build_one(SITES_DIR / site_dir / "mkdocs.yml", build_root, enable_pdf=False)
        if not ok_build:
            return False, out_build

        stylesheet_links = _extract_stylesheets(build_root / "index.html")
        toc_entries = []
        counters = {1: 0, 2: 0, 3: 0}
        used_ids: set[str] = set()
        body_parts: list[str] = []

        for doc_path in docs_in_order:
            html_path = _html_path_for_doc(docs_root, build_root, doc_path)
            if not html_path.exists():
                continue

            soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
            article_node = _select_article_node(soup)
            article_soup = BeautifulSoup(str(article_node), "html.parser")
            article_root = article_soup.find()
            if article_root is None:
                continue

            for selector in ("#site-toc", "#section-toc", ".pdf-auto-toc", "script", ".md-content__button", ".md-source-file", ".headerlink", "a[aria-label=\"Permanent link\"]"):
                for node in article_root.select(selector):
                    node.decompose()

            for heading in article_root.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
                heading.attrs.pop("data-num", None)
                heading.attrs.pop("data-number", None)
                classes = [cls for cls in heading.get("class", []) if cls != "aw-num"]
                if classes:
                    heading["class"] = classes
                elif heading.has_attr("class"):
                    del heading["class"]
                heading_text = heading.get_text(" ", strip=True).replace("¶", "").strip().lower()
                if heading_text == "inhaltsverzeichnis":
                    heading.decompose()

            _rewrite_relative_urls(article_root, html_path.parent)

            heading_tags = article_root.find_all(["h1", "h2", "h3"])
            for heading in heading_tags:
                level = int(heading.name[1])
                title_text = heading.get_text(" ", strip=True).replace("¶", "").strip()
                if level == 1:
                    counters[1] += 1
                    counters[2] = 0
                    counters[3] = 0
                    number = f"{counters[1]}"
                elif level == 2:
                    if counters[1] == 0:
                        counters[1] = 1
                    counters[2] += 1
                    counters[3] = 0
                    number = f"{counters[1]}.{counters[2]}"
                else:
                    if counters[1] == 0:
                        counters[1] = 1
                    if counters[2] == 0:
                        counters[2] = 1
                    counters[3] += 1
                    number = f"{counters[1]}.{counters[2]}.{counters[3]}"

                anchor_id = heading.get("id") or _slugify(f"{number}-{title_text}")
                while anchor_id in used_ids:
                    anchor_id = f"{anchor_id}-x"
                used_ids.add(anchor_id)
                heading["id"] = anchor_id

                prefix = article_soup.new_tag("span", attrs={"class": "pdf-heading-number"})
                prefix.string = f"{number} "
                heading.insert(0, prefix)

                toc_entries.append({
                    "level": level,
                    "number": number,
                    "title": title_text,
                    "anchor": anchor_id,
                })

            body_parts.append(f'<section class="pdf-doc">{str(article_root)}</section>')

        if not body_parts:
            return False, f"Keine HTML-Inhalte fuer PDF gefunden: {site}"

        toc_items = []
        for entry in toc_entries:
            toc_items.append(
                f'<li class="lvl-{entry["level"]}"><a href="#{entry["anchor"]}"><span class="toc-label">{entry["number"]} {entry["title"]}</span><span class="toc-page" data-target="#{entry["anchor"]}"></span></a></li>'
            )

        margin_top = config.get("pdf", "margin_top", "20mm")
        margin_right = config.get("pdf", "margin_right", "18mm")
        margin_bottom = config.get("pdf", "margin_bottom", "22mm")
        margin_left = config.get("pdf", "margin_left", "18mm")
        site_name = _site_display_name(site)
        build_info = get_version(site="portal")
        build_date = (build_info.get("build_date") or build_info.get("version_date") or "").strip()
        footer_build_text = f"Stand {build_date}" if build_date else "Stand unbekannt"

        styles = "\n".join(f'<link rel="stylesheet" href="{href}">' for href in stylesheet_links)
        html = f'''<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <title>{site_name}</title>
  {styles}
  <style>
    @page {{
      size: A4;
      margin: {margin_top} {margin_right} {margin_bottom} {margin_left};
      @bottom-left {{
        content: "{footer_build_text}";
        font-size: 9pt;
        color: #444;
      }}
      @bottom-right {{
        content: "Seite " counter(page) " / " counter(pages);
        font-size: 9pt;
        color: #444;
      }}
    }}
    body {{
      color: #111;
      font-size: 10.5pt;
      font-family: "Roboto", "Helvetica Neue", Helvetica, Arial, sans-serif;
      line-height: 1.5;
    }}
    p, li {{ font-family: inherit !important; }}
    h1 {{ font-size: 20pt; line-height: 1.18; margin: 0 0 7mm 0; }}
    h2 {{ font-size: 14pt; line-height: 1.22; margin: 0 0 4mm 0; }}
    h3 {{ font-size: 11pt; line-height: 1.26; margin: 0 0 3mm 0; }}
    .pdf-cover, .pdf-toc, .pdf-doc {{ padding: 2mm 1mm 2mm 1mm; }}
    .pdf-cover {{
      min-height: 235mm;
      display: flex;
      align-items: center;
      justify-content: center;
      text-align: center;
      margin: 0;
      page-break-after: always;
    }}
    .pdf-site-title {{
      font-size: 30pt;
      font-weight: 700;
      margin: 0;
      letter-spacing: 0.01em;
      max-width: 150mm;
    }}
    .pdf-build-date {{
      margin-top: 7mm;
      font-size: 12pt;
      color: #4b5563;
      letter-spacing: 0.02em;
      text-transform: uppercase;
    }}
    .pdf-toc-title {{
      font-size: 16pt;
      font-weight: 700;
      margin: 0 0 4mm 0;
      padding-bottom: 2mm;
      border-bottom: 0.9pt solid #111;
      text-transform: uppercase;
      letter-spacing: 0.02em;
      break-after: avoid;
      page-break-after: avoid;
    }}
    .pdf-toc {{ margin: 0 0 8mm 0; page-break-after: always; break-inside: auto; page-break-inside: auto; }}
    .pdf-toc ol {{ list-style: none; margin: 0; padding: 0; break-inside: auto !important; page-break-inside: auto !important; }}
    .pdf-toc li {{ margin: 0 0 1.4mm 0; break-inside: avoid; page-break-inside: avoid; }}
    .pdf-toc li.lvl-1 {{ font-size: 11pt; font-weight: 700; color: #111; margin-top: 3mm; }}
    .pdf-toc li.lvl-2 {{ margin-left: 10mm; font-size: 9pt; font-weight: 500; color: #555; text-transform: uppercase; }}
    .pdf-toc li.lvl-3 {{ margin-left: 18mm; font-size: 8.4pt; font-weight: 400; color: #777; }}
    .pdf-toc a {{ color: inherit; text-decoration: none; display: grid; grid-template-columns: minmax(0, 1fr) 14mm; align-items: baseline; column-gap: 2.5mm; width: 100%; }}
    .pdf-toc .toc-label {{ display: block; min-width: 0; }}
    .pdf-toc .toc-page {{ display: block; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    .pdf-toc .toc-page::after {{ content: target-counter(attr(data-target), page); }}
    .pdf-toc .toc-label::after {{ content: leader('.'); }}
    .pdf-doc {{ break-before: page; }}
    .pdf-doc:first-of-type {{ break-before: auto; }}
    .pdf-heading-number {{ font-weight: 700; color: #6b7280; margin-right: 0.28em; }}
    h1 .pdf-heading-number, h2 .pdf-heading-number, h3 .pdf-heading-number {{ font-weight: 700; }}
    .aw-num::before, .aw-num::after, h1::before, h2::before, h3::before {{ content: none !important; }}
    .headerlink, .md-content__button, .footnote-backref, .footnote-ref, a[aria-label="Permanent link"] {{ display: none !important; }}
    #site-toc, #section-toc, .pdf-auto-toc {{ display: none !important; }}
  </style>
</head>
<body>
  <section class="pdf-cover">
    <div>
      <div class="pdf-site-title">{site_name}</div>
      <div class="pdf-build-date">{footer_build_text}</div>
    </div>
  </section>
  <nav class="pdf-toc">
    <div class="pdf-toc-title">Inhaltsverzeichnis</div>
    <ol>
      {''.join(toc_items)}
    </ol>
  </nav>
  {''.join(body_parts)}
</body>
</html>'''

        out_pdf = SITE_DIR / site_route(site) / "exports" / _pdf_export_name()
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        HTML(string=html, base_url=str(build_root)).write_pdf(str(out_pdf))
        return True, f"PDF erstellt: {out_pdf}"


def pdf_flow(site: str = "all") -> Dict[str, Any]:
    """
    PDF Export = HTML-Build + serverseitig kombinierte PDF + Deploy
    """
    site = (site or "all").strip().lower()
    if site != "all":
        try:
            site = normalize_site(site)
        except KeyError:
            pass
    res: Dict[str, Any] = {"steps": [], "site": site}

    targets = ALLOWED_SITES if site == "all" else [site]
    if site != "all" and site not in ALLOWED_SITES:
        res["steps"].append("Ungueltige Site")
        res["build_ok"] = False
        res["build_output"] = f"Ungueltige Site: {site}"
        return res

    build_info = _refresh_build_metadata()
    res["version"] = build_info
    res["steps"].append(f"Build-Datum: {build_info.get('build_date')}")

    logs: list[str] = []
    for target in targets:
        ok_pdf, out_pdf = _render_site_pdf(target)
        logs.append(f"[{target}] " + ("OK" if ok_pdf else "FEHLER") + "\n" + out_pdf)
        if not ok_pdf:
            res["build_ok"] = False
            res["build_output"] = "\n\n".join(logs)
            res["steps"].append("PDF-Erzeugung FEHLER")
            return res

    res["build_ok"] = True
    res["build_output"] = "\n\n".join(logs)
    res["steps"].append("PDF-Erzeugung OK")

    ok_dep, out_dep = deploy_to_wwwroot()
    res["deploy_ok"] = ok_dep
    res["deploy_output"] = out_dep
    res["steps"].append("Deploy OK" if ok_dep else "Deploy FEHLER")
    if not ok_dep:
        return res

    pdf_urls = _pdf_urls_for_site(site)
    res["pdf_urls"] = pdf_urls
    res["pdf_url"] = pdf_urls[0] if pdf_urls else ""
    if not pdf_urls:
        res["steps"].append(f"WARN: PDF wurde nicht gefunden ({_pdf_export_name()})")

    return res

def git_checkout(branch: str) -> Tuple[bool, str]:
    ok, out = _run(["git", "checkout", branch], cwd=REPO_ROOT)
    if ok:
        return True, out
    # falls branch lokal fehlt: remote holen
    ok2, out2 = _run(["git", "fetch", GIT_REMOTE, branch], cwd=REPO_ROOT)
    if not ok2:
        return False, out + "\n" + out2
    return _run(["git", "checkout", "-B", branch, f"{GIT_REMOTE}/{branch}"], cwd=REPO_ROOT)


def git_pull(branch: str) -> Tuple[bool, str]:
    _run(["git", "config", "pull.rebase", "false"], cwd=REPO_ROOT)
    return _run(["git", "pull", "--no-rebase", GIT_REMOTE, branch], cwd=REPO_ROOT)


def git_commit_and_push_paths(message: str, add_paths: list[str], branch: str) -> tuple[bool, str]:
    """
    Commit + push nur für bestimmte Repo-Pfade (inkl. Deletes).
    WICHTIG: Wir arbeiten hier stabil ohne stash/pop.
    Empfehlung: branch="main" verwenden.

    add_paths sind Repo-relative Pfade, z.B. ["sites/allgemein/docs_draft/orga/a.md"]
    """
    if not (REPO_ROOT / ".git").exists():
        return False, f"Kein Git-Repo unter REPO_ROOT={REPO_ROOT}"

    branch = (branch or "").strip() or "main"
    if not add_paths:
        return True, "nichts zu committen (keine pfade)"

    blocked_paths = [path for path in add_paths if _is_content_git_path(path)]
    if blocked_paths and not CONTENT_GIT_SYNC_ENABLED:
        return True, _content_sync_disabled_message(blocked_paths)

    # ensure in repo
    ok, out = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=REPO_ROOT)
    if not ok:
        return False, out

    # Arbeitsbaum darf nur in den Zielpfaden dirty sein (Editor hat die Datei bereits geschrieben).
    ok, st = _run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=REPO_ROOT)
    if not ok:
        return False, st
    if st.strip():
        excluded_paths = list(add_paths) + GIT_STATUS_IGNORE_PATHS
        status_outside_cmd = [
            "git", "status", "--porcelain", "--untracked-files=all", "--", "."
        ] + _git_status_exclude_args(excluded_paths)
        ok_outside, st_outside = _run(status_outside_cmd, cwd=REPO_ROOT)
        if not ok_outside:
            return False, st_outside
        if st_outside.strip():
            return False, (
                "Working tree ist nicht clean. Bitte erst bereinigen.\n"
                "Tipp: Pruefe unerwartete Repo-Aenderungen ausserhalb von Drafts und lokalen Serverdateien.\n\n"
                + st_outside.strip()
            )

    # sync
    ok, out2 = _run(["git", "fetch", "--all", "--prune"], cwd=REPO_ROOT)
    if not ok:
        return False, out2

    # checkout branch (meist main). Falls lokal fehlt, remote holen.
    ok, out3 = _run(["git", "checkout", branch], cwd=REPO_ROOT)
    if not ok:
        # remote branch vorhanden?
        okr, rlist = _run(["git", "branch", "-r", "--list", f"{GIT_REMOTE}/{branch}"], cwd=REPO_ROOT)
        if okr and rlist.strip():
            ok, out3 = _run(["git", "checkout", "-B", branch, f"{GIT_REMOTE}/{branch}"], cwd=REPO_ROOT)
        else:
            ok, out3 = _run(["git", "checkout", "-b", branch], cwd=REPO_ROOT)
        if not ok:
            return False, out3

    _run(["git", "config", "pull.rebase", "false"], cwd=REPO_ROOT)
    ok, out4 = _run(["git", "pull", "--no-rebase", GIT_REMOTE, branch], cwd=REPO_ROOT)
    if not ok:
        return False, out4

    # stage (inkl deletes)
    ok, out5 = _run(["git", "add", "-A", "--"] + add_paths, cwd=REPO_ROOT)
    if not ok:
        return False, out5

    ok, staged = _run(["git", "diff", "--cached", "--name-only"], cwd=REPO_ROOT)
    if not ok:
        return False, staged
    if not staged.strip():
        return True, "keine aenderung (nichts zu committen)"

    ok, out6 = _run(["git", "commit", "-m", message], cwd=REPO_ROOT)
    if not ok:
        return False, out6

    ok, out7 = _run(["git", "push", GIT_REMOTE, branch], cwd=REPO_ROOT)
    if not ok:
        return False, out7

    return True, (out4 + "\n" + out6 + "\n" + out7).strip()



















