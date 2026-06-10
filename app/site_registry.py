from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SiteDef:
    key: str
    folder: str
    label: str


SITES: tuple[SiteDef, ...] = (
    SiteDef("schaden", "schaden", "Schaden"),
    SiteDef("betrieb", "betrieb", "Betrieb"),
    SiteDef("vertrieb", "vertrieb", "Vertrieb"),
    SiteDef("allgemein", "allgemein", "Allgemein"),
    SiteDef("buchhaltung", "buchhaltung", "Buchhaltung"),
    SiteDef("novas", "novas", "Novas"),
    SiteDef("datenschutz", "datenschutz", "Datenschutz"),
    SiteDef("wto", "wto", "Warentransport Online"),
    SiteDef("it-faq", "it-faq", "IT-FAQ"),
    SiteDef("testumgebung", "testumgebung", "Testumgebung"),
)

SITE_KEYS: tuple[str, ...] = tuple(site.key for site in SITES)
SITE_KEY_SET: set[str] = set(SITE_KEYS)
SITE_FOLDERS: dict[str, str] = {site.key: site.folder for site in SITES}
SITE_LABELS: dict[str, str] = {site.key: site.label for site in SITES}
FOLDER_TO_KEY: dict[str, str] = {site.folder.lower(): site.key for site in SITES}


def normalize_site(value: str | None) -> str:
    raw = (value or "").strip()
    lowered = raw.lower()
    key = FOLDER_TO_KEY.get(lowered, lowered)
    if key not in SITE_KEY_SET:
        raise KeyError(key)
    return key


def site_folder(value: str | None) -> str:
    return SITE_FOLDERS[normalize_site(value)]


def site_label(value: str | None) -> str:
    return SITE_LABELS[normalize_site(value)]
