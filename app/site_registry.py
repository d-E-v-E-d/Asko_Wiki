from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CountryDef:
    key: str
    folder: str
    label: str
    active: bool = True


@dataclass(frozen=True)
class AreaDef:
    key: str
    folder: str
    label: str
    test: bool = False


@dataclass(frozen=True)
class SiteDef:
    key: str
    folder: str
    label: str
    country_key: str
    country_label: str
    area_key: str
    area_label: str
    route: str
    active: bool = True
    test: bool = False


COUNTRIES: tuple[CountryDef, ...] = (
    CountryDef("at", "at", "Österreich", True),
    CountryDef("de", "de", "Deutschland", True),
    CountryDef("si", "si", "Slowenien", True),
    CountryDef("it", "it", "Italien", True),
    CountryDef("ro", "ro", "Rumänien", True),
)

AREAS: tuple[AreaDef, ...] = (
    AreaDef("allgemein", "allgemein", "Allgemein"),
    AreaDef("schaden", "schaden", "Schaden"),
    AreaDef("betrieb", "betrieb", "Betrieb"),
    AreaDef("vertrieb", "vertrieb", "Vertrieb"),
    AreaDef("buchhaltung", "buchhaltung", "Buchhaltung"),
    AreaDef("novas", "novas", "Novas"),
    AreaDef("datenschutz", "datenschutz", "Datenschutz"),
    AreaDef("wto", "wto", "Warentransport Online"),
    AreaDef("it-faq", "it-faq", "IT-FAQ"),
    AreaDef("testumgebung", "testumgebung", "Testumgebung", True),
)


def _build_sites() -> tuple[SiteDef, ...]:
    sites: list[SiteDef] = []
    for country in COUNTRIES:
        for area in AREAS:
            key = f"{country.key}-{area.key}"
            folder = f"{country.folder}/{area.folder}"
            label = f"{country.label} / {area.label}"
            route = f"{country.folder}/{area.folder}"
            sites.append(
                SiteDef(
                    key=key,
                    folder=folder,
                    label=label,
                    country_key=country.key,
                    country_label=country.label,
                    area_key=area.key,
                    area_label=area.label,
                    route=route,
                    active=country.active,
                    test=area.test,
                )
            )
    return tuple(sites)


SITES: tuple[SiteDef, ...] = _build_sites()

COUNTRY_KEYS: tuple[str, ...] = tuple(country.key for country in COUNTRIES)
COUNTRY_KEY_SET: set[str] = set(COUNTRY_KEYS)
COUNTRY_FOLDERS: dict[str, str] = {country.key: country.folder for country in COUNTRIES}
COUNTRY_LABELS: dict[str, str] = {country.key: country.label for country in COUNTRIES}

AREA_KEYS: tuple[str, ...] = tuple(area.key for area in AREAS)
AREA_KEY_SET: set[str] = set(AREA_KEYS)
AREA_FOLDERS: dict[str, str] = {area.key: area.folder for area in AREAS}
AREA_LABELS: dict[str, str] = {area.key: area.label for area in AREAS}

SITE_KEYS: tuple[str, ...] = tuple(site.key for site in SITES)
SITE_KEY_SET: set[str] = set(SITE_KEYS)
SITE_FOLDERS: dict[str, str] = {site.key: site.folder for site in SITES}
SITE_LABELS: dict[str, str] = {site.key: site.label for site in SITES}
SITE_ROUTES: dict[str, str] = {site.key: site.route for site in SITES}
FOLDER_TO_KEY: dict[str, str] = {site.folder.lower(): site.key for site in SITES}
ROUTE_TO_KEY: dict[str, str] = {site.route.lower(): site.key for site in SITES}
LEGACY_AREA_TO_AT_KEY: dict[str, str] = {area.key: f"at-{area.key}" for area in AREAS}


def normalize_country(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in COUNTRY_KEY_SET:
        return raw
    raise KeyError(raw)


def normalize_area(value: str | None) -> str:
    raw = (value or "").strip().lower()
    if raw in AREA_KEY_SET:
        return raw
    raise KeyError(raw)


def normalize_site(value: str | None) -> str:
    raw = (value or "").strip().replace("\\", "/")
    lowered = raw.lower().strip("/")
    key = (
        FOLDER_TO_KEY.get(lowered)
        or ROUTE_TO_KEY.get(lowered)
        or LEGACY_AREA_TO_AT_KEY.get(lowered)
        or lowered
    )
    if key not in SITE_KEY_SET:
        raise KeyError(key)
    return key


def site_folder(value: str | None) -> str:
    return SITE_FOLDERS[normalize_site(value)]


def site_route(value: str | None) -> str:
    return SITE_ROUTES[normalize_site(value)]


def site_label(value: str | None) -> str:
    return SITE_LABELS[normalize_site(value)]


def site_country(value: str | None) -> str:
    return next(site.country_key for site in SITES if site.key == normalize_site(value))


def site_area(value: str | None) -> str:
    return next(site.area_key for site in SITES if site.key == normalize_site(value))
