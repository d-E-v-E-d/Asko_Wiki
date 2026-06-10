#!/usr/bin/env bash
set -euo pipefail

# Intentionally disabled:
# Arbeitsanweisung content under sites/ and review/ must not be synchronized to GitHub.

LOG_ROOT="${BACKUP_ROOT:-/srv/arbeitsanweisung/backups/local-snapshots}"
LOG_DIR="${LOG_ROOT}/logs"
LOG_FILE="${LOG_DIR}/nightly_git_sync.log"
LOCK_FILE="${LOG_ROOT}/.nightly_git_sync.lock"

umask 027
mkdir -p "${LOG_ROOT}" "${LOG_DIR}"
touch "${LOG_FILE}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [WARN] Nightly git sync already running" | tee -a "${LOG_FILE}"
  exit 0
fi

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [INFO] Nightly Git sync disabled: sites/review are not synchronized to GitHub." | tee -a "${LOG_FILE}"
exit 0
