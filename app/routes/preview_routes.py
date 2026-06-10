from fastapi import APIRouter, Depends, HTTPException, Request, status
from pygments.formatters import HtmlFormatter
from app.auth.deps import require_role, CurrentUser
import re
import os
import posixpath
from pathlib import Path
from markdown import Markdown
from bs4 import BeautifulSoup
from app.runtime_paths import get_site_build_root, get_sites_root
from app.site_registry import SITE_KEY_SET, normalize_site, site_folder

router = APIRouter(prefix="/preview", tags=["preview"])

# =========================
# Konfiguration / Sites
# =========================
SITE_BUILD_ROOT = get_site_build_root()

ALLOWED_SITES = SITE_KEY_SET

# Absoluter Pfad damit Existenzchecks stabil sind
SITES_ROOT = get_sites_root()

def _norm_site(site: str | None) -> str:
    try:
        s = normalize_site(site or "schaden")
    except KeyError:
        s = ""
    if s not in ALLOWED_SITES:
        raise HTTPException(status_code=400, detail="Invalid site")
    return s

# =========================
# Markdown/HTML Image Rewrites
# =========================
MD_IMG_RE = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
HTML_IMG_RE = re.compile(r'(<img\b[^>]*\bsrc=)(["\'])([^"\']+)\2', re.IGNORECASE)

def _is_external_or_special(url: str) -> bool:
    u = (url or "").strip()
    return u.startswith(("http://", "https://", "#", "data:"))

def _asset_exists(site: str, rel_path: str) -> tuple[bool, bool]:
    """
    rel_path: path relative within docs root (e.g. "Wirtschaftsraum/img.png")
    returns: (exists_in_draft, exists_in_live)
    """
    p = (rel_path or "").replace("\\", "/").lstrip("/")
    folder = site_folder(site)
    draft = (SITES_ROOT / folder / "docs_draft" / p).exists()
    live  = (SITES_ROOT / folder / "docs" / p).exists()
    return draft, live

def _resolve_rel_under_md(md_file: str, url0: str) -> str:
    """
    Resolves url0 (relative) against md_file directory, POSIX-normalized.
    Keeps case from md_file/url0 (important on Linux).
    """
    md_file = (md_file or "").replace("\\", "/").lstrip("/")
    base_dir = posixpath.dirname(md_file).strip("/")  # e.g. "Wirtschaftsraum"
    rel = (url0 or "").strip().strip('"').strip("'").lstrip("./")

    joined = posixpath.normpath(posixpath.join(base_dir, rel)) if base_dir else posixpath.normpath(rel)
    # no traversal
    if joined.startswith(".."):
        return rel
    return joined

def _rewrite_url_to_best_mount(site: str, md_file: str, url0: str) -> str:
    """
    Draft-first:
      - If relative: resolve vs md_file folder -> check docs_draft first -> /docs_draft/<site>/...
      - Else fallback /docs/<site>/...
    """
    url0 = (url0 or "").strip().strip('"').strip("'")

    # Never touch external/special
    if _is_external_or_special(url0):
        return url0

    # Keep already-correct absolute mounts
    if url0.startswith(f"/docs_draft/{site}/") or url0.startswith(f"/docs/{site}/"):
        return url0

    # Leave other absolute server paths alone
    if url0.startswith("/"):
        return url0

    # Relative -> resolve and choose draft/live
    joined = _resolve_rel_under_md(md_file, url0)
    exists_draft, exists_live = _asset_exists(site, joined)

    if exists_draft:
        return f"/docs_draft/{site}/{joined}".replace("//", "/")
    # if not in draft, fallback to live (even if not exists, still deterministic)
    return f"/docs/{site}/{joined}".replace("//", "/")

def _rewrite_image_paths(text: str, md_file: str, site: str) -> str:
    """
    Draft-first, live-fallback:
    - relative URLs werden relativ zum md_file-Verzeichnis aufgelöst
    - wenn Datei in docs_draft existiert -> /docs_draft/<site>/...
    - sonst -> /docs/<site>/...
    - Spezialfälle: assets/... gilt als site-root (nicht relativ zum md-file)
    """

    def rewrite_one(url0: str) -> str:
        url0 = (url0 or "").strip().strip('"').strip("'")

        # Extern/Special/absolute: nur /docs... /docs_draft... ggf. beibehalten
        if _is_external_or_special(url0):
            return url0
        if url0.startswith(f"/docs_draft/{site}/") or url0.startswith(f"/docs/{site}/"):
            return url0
        if url0.startswith("/"):
            return url0  # andere absolute Pfade nicht anfassen

        # RELATIV:
        md_file_norm = (md_file or "").replace("\\", "/").lstrip("/")
        base_dir = posixpath.dirname(md_file_norm).strip("/")
        rel = url0.lstrip("./")

        # assets/... ist site-root
        if rel.startswith("assets/"):
            joined = posixpath.normpath(rel)

            exists_draft, exists_live = _asset_exists(site, joined)
            if exists_draft:
                return f"/docs_draft/{site}/{joined}"
            if exists_live:
                return f"/docs/{site}/{joined}"

            return f"/docs_draft/{site}/{joined}"
        else:
            joined = posixpath.normpath(posixpath.join(base_dir, rel)) if base_dir else posixpath.normpath(rel)

        # traversal block
        if joined.startswith(".."):
            return url0

        exists_draft, exists_live = _asset_exists(site, joined)
        if exists_draft:
            return f"/docs_draft/{site}/{joined}".replace("//", "/")
        return f"/docs/{site}/{joined}".replace("//", "/")

    # Markdown images
    def md_repl(m):
        alt = m.group(1)
        raw = (m.group(2) or "").strip()
        parts = raw.split()
        url0 = parts[0]
        new_url = rewrite_one(url0)
        if len(parts) > 1:
            return f'![{alt}]({new_url} {" ".join(parts[1:])})'
        return f'![{alt}]({new_url})'

    out = MD_IMG_RE.sub(md_repl, text)

    # HTML <img> (raw html in markdown)
    def html_repl(m):
        prefix, quote, url0 = m.group(1), m.group(2), m.group(3)
        return f"{prefix}{quote}{rewrite_one(url0)}{quote}"

    out = HTML_IMG_RE.sub(html_repl, out)
    return out


def _markdown_path_to_site_url(site: str, md_path: str, anchor: str = "") -> str:
    rel = (md_path or "").replace("\\", "/").lstrip("/")
    if not rel:
        base = f"/{site}/"
    elif rel.lower() == "index.md":
        base = f"/{site}/"
    elif rel.lower().endswith("/index.md"):
        base = f"/{site}/{rel[:-len('index.md')]}"
    elif rel.lower().endswith(".md"):
        base = f"/{site}/{rel[:-3]}/"
    else:
        base = f"/{site}/{rel}"

    if not base.endswith("/") and "." not in posixpath.basename(base):
        base += "/"

    if anchor:
        return f"{base}#{anchor}"
    return base


def _rewrite_link_href(site: str, md_file: str, href: str) -> str:
    raw = (href or "").strip()
    if _is_external_or_special(raw):
        return raw

    if raw.startswith(f"/{site}/") or raw.startswith("/site/") or raw.startswith("/docs/") or raw.startswith("/docs_draft/"):
        return raw

    if raw.startswith("/"):
        return raw

    path_part, sep, anchor = raw.partition("#")
    resolved = _resolve_rel_under_md(md_file, path_part or "")
    if resolved.lower().endswith(".md"):
        return _markdown_path_to_site_url(site, resolved, anchor)
    return raw


def _rewrite_anchor_links(html: str, md_file: str, site: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for link in soup.find_all("a", href=True):
        href = link.get("href") or ""
        link["href"] = _rewrite_link_href(site, md_file, href)
    return str(soup)

# =========================
# Fix: Headings dürfen nicht als Codeblock enden
# =========================
RE_HEADING_INDENT = re.compile(r'(?m)^[ \t]{4,}(#{1,6}\s)')
def _normalize_heading_indent(text: str) -> str:
    return RE_HEADING_INDENT.sub(r"\1", text)

# =========================
# Stylesheets: Material aus build output
# =========================
def _get_site_stylesheets(site: str) -> list[str]:
    base = SITE_BUILD_ROOT / site / "assets" / "stylesheets"
    if not base.exists():
        return []

    css_files = list(base.glob("*.css"))

    def key(p: Path):
        n = p.name.lower()
        if n.startswith("main"):
            return (0, n)
        if n.startswith("palette"):
            return (1, n)
        return (5, n)

    css_files = sorted(css_files, key=key)
    return [f"/site/{site}/assets/stylesheets/{p.name}" for p in css_files]

# =========================
# Markdown Renderer (MkDocs-nah)
# =========================
def _build_markdown_renderer() -> Markdown:
    return Markdown(
        extensions=[
            "admonition",
            "tables",
            "attr_list",
            "toc",
        ],
        extension_configs={
            "toc": {"permalink": True},
        },
        output_format="html5",
    )

def _render_markdown_py(md_text: str) -> str:
    renderer = _build_markdown_renderer()
    return renderer.convert(md_text)

@router.post("")
@router.post("/")
async def preview(request: Request, user: CurrentUser = Depends(require_role("editor"))):
    try:
        content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()

        text = ""
        md_file = ""
        site = "schaden"

        if content_type == "application/json":
            data = await request.json()
            if not isinstance(data, dict) or "markdown" not in data:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="JSON must contain 'markdown'")
            text = data.get("markdown") or ""
            md_file = data.get("file") or ""
            site = _norm_site(data.get("site"))

        elif content_type in ("multipart/form-data", "application/x-www-form-urlencoded"):
            form = await request.form()
            if "markdown" not in form:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Form must contain 'markdown'")
            text = form.get("markdown") or ""
            md_file = form.get("file") or ""
            site = _norm_site(form.get("site"))

        else:
            body = await request.body()
            text = body.decode("utf-8", errors="ignore")
            md_file = ""
            site = _norm_site(None)

        # normalize headings (avoid accidental code blocks)
        text = _normalize_heading_indent(text)

        # rewrite images (draft-first)
        if md_file:
            text = _rewrite_image_paths(text, md_file, site)

        inner = _render_markdown_py(text)
        if md_file:
            inner = _rewrite_anchor_links(inner, md_file, site)
        html = f'<div class="md-typeset">{inner}</div>'

        stylesheets = _get_site_stylesheets(site)
        css = HtmlFormatter().get_style_defs(".codehilite")

        return {"html": html, "css": css, "stylesheets": stylesheets}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {e}")
