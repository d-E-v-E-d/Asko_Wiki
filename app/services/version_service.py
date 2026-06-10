# app/services/version_service.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Any, Optional
import datetime
import yaml  # PyYAML
from app.site_registry import SITE_KEYS, site_folder, normalize_site

# Repo Root: .../app
REPO_ROOT = Path(__file__).resolve().parents[2]

PORTAL_MKDOCS = REPO_ROOT / "portal" / "mkdocs.yml"
SITES_DIR = REPO_ROOT / "sites"

# Deine Sites (wie von dir genannt)
ALLOWED_SITES = list(SITE_KEYS)


def _mkdocs_path_for(site: str = "portal") -> Path:
    """
    site:
      - "portal" => portal/mkdocs.yml
      - "<area>" => sites/<area>/mkdocs.yml
    """
    s = (site or "portal").strip().lower()

    if s in ("portal", "root", "landing"):
        return PORTAL_MKDOCS

    try:
        s = normalize_site(s)
    except KeyError:
        pass

    if s not in ALLOWED_SITES:
        raise FileNotFoundError(f"Unbekannte Site '{s}' (kein mkdocs.yml Pfad definiert)")

    return SITES_DIR / site_folder(s) / "mkdocs.yml"


def _load_mkdocs(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"mkdocs.yml nicht gefunden: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _save_mkdocs(path: Path, cfg: Dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def get_version(site: str = "portal") -> Dict[str, str]:
    """
    Liest version/version_date aus extra in der gewünschten mkdocs.yml.
    Standard: portal (global).
    """
    mk = _mkdocs_path_for(site)
    cfg = _load_mkdocs(mk)
    extra = cfg.get("extra") or {}
    return {
        "version": str(extra.get("version", "")),
        "version_date": str(extra.get("version_date", "")),
        "build_date": str(extra.get("version_date", "")),
    }


def set_version(
        version: str,
        date: Optional[str] = None,
        site: str = "portal",
        mirror_to_sites: bool = False,
) -> Dict[str, str]:
    """
    Setzt version/version_date in extra der gewünschten mkdocs.yml.

    mirror_to_sites=True:
      schreibt dieselbe Version zusätzlich in alle sites/<area>/mkdocs.yml,
      damit Footer/Meta in jeder Site konsistent ist.
    """
    if not date:
        date = datetime.date.today().isoformat()

    # 1) Primärdatei schreiben
    mk = _mkdocs_path_for(site)
    cfg = _load_mkdocs(mk)
    extra = cfg.get("extra") or {}
    cfg["extra"] = extra
    extra["version"] = version
    extra["version_date"] = date
    _save_mkdocs(mk, cfg)

    # 2) Optional spiegeln
    if mirror_to_sites:
        for s in ALLOWED_SITES:
            p = _mkdocs_path_for(s)
            if not p.exists():
                # Site ist evtl. noch nicht angelegt -> überspringen
                continue
            c = _load_mkdocs(p)
            ex = c.get("extra") or {}
            c["extra"] = ex
            ex["version"] = version
            ex["version_date"] = date
            _save_mkdocs(p, c)

    return {"version": version, "version_date": date, "build_date": date}
