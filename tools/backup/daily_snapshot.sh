#!/usr/bin/env bash
set -euo pipefail

# Daily local snapshot backup for the Arbeitsanweisung workspace plus local rollback versions.
# Defaults can be overridden via environment variables or /etc/asko-backup/backup.env.

APP_ROOT="${APP_ROOT:-/srv/arbeitsanweisung/app}"
VERSIONS_ROOT="${VERSIONS_ROOT:-/srv/arbeitsanweisung/versions}"
BACKUP_ROOT="${BACKUP_ROOT:-/srv/arbeitsanweisung/backups/local-snapshots}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
LOG_DIR="${BACKUP_ROOT}/logs"
LOG_FILE="${LOG_DIR}/daily_snapshot.log"
LOCK_FILE="${BACKUP_ROOT}/.daily_snapshot.lock"

umask 027
mkdir -p "${BACKUP_ROOT}" "${LOG_DIR}"
touch "${LOG_FILE}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [WARN] Daily snapshot already running" | tee -a "${LOG_FILE}"
  exit 0
fi

log() {
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') $*" | tee -a "${LOG_FILE}"
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    log "[ERROR] Missing command: $1"
    exit 1
  fi
}

require_cmd rsync
require_cmd find
require_cmd du

if [[ ! -d "${APP_ROOT}" ]]; then
  log "[ERROR] APP_ROOT does not exist: ${APP_ROOT}"
  exit 1
fi

ts="$(date +'%Y-%m-%d_%H%M%S')"
snapshot_dir="${BACKUP_ROOT}/snapshot-${ts}"
tmp_dir="${BACKUP_ROOT}/.snapshot-${ts}.tmp"
latest_link="${BACKUP_ROOT}/latest"

link_dest_opt=()
if [[ -L "${latest_link}" ]] && [[ -d "$(readlink -f "${latest_link}")" ]]; then
  prev_snapshot="$(readlink -f "${latest_link}")"
  link_dest_opt=(--link-dest="${prev_snapshot}")
fi

log "[INFO] Starting daily snapshot"
log "[INFO] App source: ${APP_ROOT}"
log "[INFO] Versions source: ${VERSIONS_ROOT}"
log "[INFO] Target: ${snapshot_dir}"

mkdir -p "${tmp_dir}"
rsync -aHAX --numeric-ids --delete "${link_dest_opt[@]}" \
  "${APP_ROOT}/" "${tmp_dir}/"

version_link_dest_opt=()
if [[ -L "${latest_link}" ]] && [[ -d "$(readlink -f "${latest_link}")/versions" ]]; then
  prev_snapshot="$(readlink -f "${latest_link}")"
  version_link_dest_opt=(--link-dest="${prev_snapshot}/versions")
fi

if [[ -d "${VERSIONS_ROOT}" ]]; then
  mkdir -p "${tmp_dir}/versions"
  rsync -aHAX --numeric-ids --delete "${version_link_dest_opt[@]}" \
    "${VERSIONS_ROOT}/" "${tmp_dir}/versions/"
else
  log "[WARN] Versions source does not exist yet: ${VERSIONS_ROOT}"
  mkdir -p "${tmp_dir}/versions"
fi

bytes="$(du -sb "${tmp_dir}" | awk '{print $1}')"
files="$(find "${tmp_dir}" -type f | wc -l | awk '{print $1}')"
dirs="$(find "${tmp_dir}" -type d | wc -l | awk '{print $1}')"

cat > "${tmp_dir}/backup_metadata.json" <<EOF
{
  "type": "daily_snapshot",
  "created_at_utc": "$(date -u +'%Y-%m-%dT%H:%M:%SZ')",
  "source": "${APP_ROOT}",
  "versions_source": "${VERSIONS_ROOT}",
  "retention_days": ${RETENTION_DAYS},
  "file_count": ${files},
  "dir_count": ${dirs},
  "bytes": ${bytes},
  "hostname": "$(hostname)"
}
EOF

mv "${tmp_dir}" "${snapshot_dir}"
ln -sfn "${snapshot_dir}" "${latest_link}"

find "${BACKUP_ROOT}" -maxdepth 1 -type d -name 'snapshot-*' -mtime +"${RETENTION_DAYS}" -exec rm -rf {} +

log "[INFO] Snapshot completed: ${snapshot_dir} (files=${files}, bytes=${bytes})"
