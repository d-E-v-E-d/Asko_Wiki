#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/srv/arbeitsanweisung/app"
SERVICE="arbeitsanweisung"
SITE_DIR="/srv/arbeitsanweisung/app/site"
VENV="/srv/arbeitsanweisung/venv"
MKDOCS="${VENV}/bin/mkdocs"
PIP="${VENV}/bin/pip"
LOCK_FILE="/tmp/deploy_arbeitsanweisung.lock"
BUILD_TMP="${SITE_DIR}.new.$$"
TARGET_BRANCH="main"
CONTENT_SNAPSHOT=""

# Areas -> /<bereich>/; wird nach dem Git-Update dynamisch aus lokalen sites/*/mkdocs.yml geladen.
AREAS=()
CONTENT_PATHS=(sites review)

log() {
  printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    log "ERROR: command not found: $1"
    exit 1
  }
}

cleanup() {
  rc=$?
  rm -rf "$BUILD_TMP" 2>/dev/null || true
  if [[ -n "${CONTENT_SNAPSHOT}" && -d "${CONTENT_SNAPSHOT}" ]]; then
    restore_content_snapshot "$CONTENT_SNAPSHOT" 2>/dev/null || true
    rm -rf "$CONTENT_SNAPSHOT" 2>/dev/null || true
  fi
  if [[ $rc -ne 0 ]]; then
    log "Deploy FAILED (exit=$rc)"
  fi
  exit $rc
}
trap cleanup EXIT

timestamp() {
  date '+%Y%m%d-%H%M%S'
}

load_areas() {
  local area_dir
  AREAS=()
  while IFS= read -r area_dir; do
    AREAS+=("${area_dir#sites/}")
  done < <(find sites -mindepth 2 -maxdepth 2 -type d -exec test -f '{}/mkdocs.yml' ';' -print | sort)

  if [[ ${#AREAS[@]} -eq 0 ]]; then
    log "ERROR: no MkDocs areas found under sites/*/*/mkdocs.yml"
    exit 1
  fi
}

area_route() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

preserve_content_snapshot() {
  local snapshot_dir="$1"
  local path
  rm -rf "$snapshot_dir"
  mkdir -p "$snapshot_dir"
  for path in "${CONTENT_PATHS[@]}"; do
    if [[ -e "$path" ]]; then
      mkdir -p "${snapshot_dir}/${path}"
      rsync -a --delete "${path}/" "${snapshot_dir}/${path}/"
    fi
  done
}

restore_content_snapshot() {
  local snapshot_dir="$1"
  local path
  for path in "${CONTENT_PATHS[@]}"; do
    if [[ -e "${snapshot_dir}/${path}" ]]; then
      mkdir -p "$path"
      if [[ "$path" == "sites" ]]; then
        # Code-only Repo bringt technische sites/<land>/<bereich>-Skeletons mit.
        # Lokale Inhalte werden daruebergelegt, damit die Skeletons nicht geloescht werden.
        rsync -a "${snapshot_dir}/${path}/" "${path}/"
      else
        rm -rf "$path"
        mkdir -p "$path"
        rsync -a --delete "${snapshot_dir}/${path}/" "${path}/"
      fi
    fi
  done
}

migrate_legacy_flat_sites_to_at() {
  local legacy
  local area
  local target
  for legacy in sites/*; do
    [[ -d "$legacy" ]] || continue
    area="$(basename "$legacy")"
    [[ "$area" =~ ^(at|de|si|it|ro)$ ]] && continue
    [[ -f "$legacy/mkdocs.yml" || -d "$legacy/docs" || -d "$legacy/docs_draft" ]] || continue

    target="sites/at/$area"
    mkdir -p "$target/docs" "$target/docs_draft"
    if [[ -d "$legacy/docs" ]]; then
      rsync -a "$legacy/docs/" "$target/docs/"
    fi
    if [[ -d "$legacy/docs_draft" ]]; then
      rsync -a "$legacy/docs_draft/" "$target/docs_draft/"
    fi
    rm -rf "$legacy"
    log "Migrated legacy site $area -> at/$area"
  done
}

sync_shared_mkdocs_assets() {
  local area
  local docs_dir
  if [[ ! -d shared ]]; then
    log "shared/ missing -> skip shared MkDocs assets sync"
    return
  fi
  for area in "${AREAS[@]}"; do
    if [[ -d shared/overrides ]]; then
      mkdir -p "sites/${area}/overrides"
      rsync -a "shared/overrides/" "sites/${area}/overrides/"
    fi
    if [[ -d shared/assets ]]; then
      for docs_dir in "sites/${area}/docs" "sites/${area}/docs_draft"; do
        if [[ -d "$docs_dir" ]]; then
          mkdir -p "${docs_dir}/assets"
          rsync -a "shared/assets/" "${docs_dir}/assets/"
        fi
      done
    fi
  done
}

# Prevent parallel deploys
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
  log "Another deploy is running (lock: $LOCK_FILE)."
  exit 1
fi

# Safety guard for rm/rsync targets
if [[ "$SITE_DIR" != "/srv/arbeitsanweisung/app/site" ]]; then
  log "ERROR: SITE_DIR guard triggered ($SITE_DIR)"
  exit 1
fi

require_cmd git
require_cmd sudo
require_cmd systemctl
require_cmd nginx
require_cmd rsync
require_cmd flock

if [[ ! -x "$MKDOCS" ]]; then
  log "ERROR: mkdocs executable not found: $MKDOCS"
  exit 1
fi
if [[ ! -x "$PIP" ]]; then
  log "ERROR: pip executable not found: $PIP"
  exit 1
fi

cd "$APP_DIR"

log "[1/6] Sync main (hard reset)"
git fetch --prune origin
CONTENT_SNAPSHOT="$(mktemp -d /tmp/asko-content.XXXXXX)"
log "Preserve local content paths; no sites/review push to GitHub"
preserve_content_snapshot "$CONTENT_SNAPSHOT"
git fetch --prune origin
git reset --hard origin/main
git clean -fd
restore_content_snapshot "$CONTENT_SNAPSHOT"
migrate_legacy_flat_sites_to_at
rm -rf "$CONTENT_SNAPSHOT"
CONTENT_SNAPSHOT=""
load_areas
log "Sync shared MkDocs assets into local sites"
sync_shared_mkdocs_assets

log "[2/6] Python deps"
if [[ -f requirements.txt ]]; then
  "$PIP" install -r requirements.txt
else
  log "requirements.txt missing -> skip"
fi

log "[3/6] MkDocs build (portal + areas)"
rm -rf "$BUILD_TMP"
mkdir -p "$BUILD_TMP"

if [[ ! -f portal/mkdocs.yml ]]; then
  log "ERROR: portal/mkdocs.yml not found"
  exit 1
fi

log "  - build: portal"
"$MKDOCS" build -c -f portal/mkdocs.yml -d "$BUILD_TMP"

for area in "${AREAS[@]}"; do
  cfg="sites/${area}/mkdocs.yml"
  route="$(area_route "$area")"
  if [[ -f "$cfg" ]]; then
    if ! find "sites/${area}/docs" -type f -name '*.md' -print -quit 2>/dev/null | grep -q .; then
      log "  - skip: ${area} (no markdown content)"
      continue
    fi
    log "  - build: ${area} -> /${route}/"
    "$MKDOCS" build -c -f "$cfg" -d "${BUILD_TMP}/${route}"
  else
    log "  - skip: ${area} (missing ${cfg})"
  fi
done

log "[4/6] Sync build output"
sudo mkdir -p "$SITE_DIR"
sudo rsync -a --delete "${BUILD_TMP}/" "${SITE_DIR}/"
sudo chown -R admmd001:arbeitsanw "$SITE_DIR"

log "[5/6] Restart service"
sudo systemctl restart "$SERVICE"

log "[6/6] Reload nginx"
sudo nginx -t
sudo systemctl reload nginx

log "Deploy OK"

