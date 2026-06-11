#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/arbeitsanweisung/app}"
MODE="all"
DRY_RUN=0

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

usage() {
  cat <<'USAGE'
Usage: bash scripts/bootstrap_country_content.sh [de|si|all] [--dry-run]

Kopiert einmalig lokale Live-Inhalte aus Oesterreich in neue Laenderbereiche.
- de: IT-FAQ und WTO vollstaendig, Datenschutz nur Markdown/.pages ohne Anlagen
- si: alle AT-Bereiche vollstaendig

Sicherheitsregel: Zielbereiche mit vorhandenen .md-Dateien werden uebersprungen.
USAGE
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log "ERROR: command not found: $1"
    exit 1
  }
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    de|si|all)
      MODE="$1"
      ;;
    --dry-run)
      DRY_RUN=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 1
      ;;
  esac
  shift
done

site_docs_have_markdown() {
  local docs_dir="$1"
  [[ -d "$docs_dir" ]] && find "$docs_dir" -type f -name '*.md' -print -quit 2>/dev/null | grep -q .
}

copy_docs_from_at() {
  local country="$1"
  local area="$2"
  local mode="${3:-full}"
  local source_docs="sites/at/${area}/docs"
  local target_docs="sites/${country}/${area}/docs"
  local rsync_args=(-a)

  [[ "$country" != "at" ]] || return 0
  [[ -d "$source_docs" ]] || {
    log "SKIP ${country^^}/${area}: Quelle fehlt (${source_docs})"
    return 0
  }
  mkdir -p "$target_docs"

  if site_docs_have_markdown "$target_docs"; then
    log "SKIP ${country^^}/${area}: Ziel enthaelt bereits Markdown"
    return 0
  fi

  if ! site_docs_have_markdown "$source_docs"; then
    log "SKIP ${country^^}/${area}: AT-Quelle enthaelt keine Markdown-Dateien"
    return 0
  fi

  if [[ "$DRY_RUN" -eq 1 ]]; then
    rsync_args+=(--dry-run --itemize-changes)
  fi

  if [[ "$mode" == "markdown-only" ]]; then
    rsync "${rsync_args[@]}" \
      --include='*/' \
      --include='*.md' \
      --include='.pages' \
      --exclude='*' \
      "$source_docs/" "$target_docs/"
    log "BOOTSTRAP ${country^^}/${area}: Markdown-Struktur aus AT uebernommen (Anlagen/Assets ausgelassen)"
  else
    rsync "${rsync_args[@]}" "$source_docs/" "$target_docs/"
    log "BOOTSTRAP ${country^^}/${area}: Live-Inhalte aus AT uebernommen"
  fi
}

bootstrap_de() {
  copy_docs_from_at "de" "it-faq" "full"
  copy_docs_from_at "de" "wto" "full"
  copy_docs_from_at "de" "datenschutz" "markdown-only"
}

bootstrap_si() {
  local at_area_dir
  local area
  for at_area_dir in sites/at/*; do
    [[ -d "$at_area_dir" ]] || continue
    area="$(basename "$at_area_dir")"
    [[ -f "$at_area_dir/mkdocs.yml" ]] || continue
    copy_docs_from_at "si" "$area" "full"
  done
}

require_cmd rsync

if [[ -d "$APP_DIR" ]]; then
  cd "$APP_DIR"
fi

if [[ ! -d sites/at ]]; then
  log "ERROR: sites/at nicht gefunden. Bitte im App-Root ausfuehren oder APP_DIR setzen."
  exit 1
fi

case "$MODE" in
  de)
    bootstrap_de
    ;;
  si)
    bootstrap_si
    ;;
  all)
    bootstrap_de
    bootstrap_si
    ;;
esac

if [[ "$DRY_RUN" -eq 1 ]]; then
  log "Dry-run abgeschlossen. Es wurden keine Dateien kopiert."
else
  log "Bootstrap abgeschlossen. Danach normal deployen: bash scripts/deploy.sh"
fi

