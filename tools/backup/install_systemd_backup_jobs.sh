#!/usr/bin/env bash
set -euo pipefail

# Installs backup scripts and systemd timers on Ubuntu.
# Must run as root on target server.

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root (sudo)."
  exit 1
fi

REPO_DIR="${1:-/srv/arbeitsanweisung/app}"
SCRIPT_TARGET_DIR="/usr/local/bin"
SYSTEMD_DIR="/etc/systemd/system"
CONF_DIR="/etc/asko-backup"
ENV_FILE="${CONF_DIR}/backup.env"

mkdir -p "${SCRIPT_TARGET_DIR}" "${CONF_DIR}"

install -m 750 "${REPO_DIR}/tools/backup/daily_snapshot.sh" "${SCRIPT_TARGET_DIR}/asko-daily-snapshot.sh"
install -m 750 "${REPO_DIR}/tools/backup/weekly_git_bundle.sh" "${SCRIPT_TARGET_DIR}/asko-weekly-git-bundle.sh"
install -m 750 "${REPO_DIR}/tools/backup/nightly_git_sync.sh" "${SCRIPT_TARGET_DIR}/asko-nightly-git-sync.sh"

install -m 644 "${REPO_DIR}/tools/backup/systemd/asko-backup-daily.service" "${SYSTEMD_DIR}/asko-backup-daily.service"
install -m 644 "${REPO_DIR}/tools/backup/systemd/asko-backup-daily.timer" "${SYSTEMD_DIR}/asko-backup-daily.timer"
install -m 644 "${REPO_DIR}/tools/backup/systemd/asko-backup-weekly-bundle.service" "${SYSTEMD_DIR}/asko-backup-weekly-bundle.service"
install -m 644 "${REPO_DIR}/tools/backup/systemd/asko-backup-weekly-bundle.timer" "${SYSTEMD_DIR}/asko-backup-weekly-bundle.timer"
install -m 644 "${REPO_DIR}/tools/backup/systemd/asko-nightly-git-sync.service" "${SYSTEMD_DIR}/asko-nightly-git-sync.service"
install -m 644 "${REPO_DIR}/tools/backup/systemd/asko-nightly-git-sync.timer" "${SYSTEMD_DIR}/asko-nightly-git-sync.timer"

if [[ ! -f "${ENV_FILE}" ]]; then
  cat > "${ENV_FILE}" <<EOF
APP_ROOT=/srv/arbeitsanweisung/app
VERSIONS_ROOT=/srv/arbeitsanweisung/versions
BACKUP_ROOT=/srv/arbeitsanweisung/backups/local-snapshots
RETENTION_DAYS=14
BUNDLE_ROOT=/srv/arbeitsanweisung/backups/git-bundles
BUNDLE_RETENTION_WEEKS=12
GIT_SYNC_BRANCH=main
GIT_SYNC_PATHS=""
EOF
  chmod 640 "${ENV_FILE}"
fi

systemctl daemon-reload
systemctl enable --now asko-backup-daily.timer
systemctl enable --now asko-backup-weekly-bundle.timer
systemctl enable --now asko-nightly-git-sync.timer

echo "Installed. Check status with:"
echo "  systemctl status asko-backup-daily.timer asko-backup-weekly-bundle.timer asko-nightly-git-sync.timer"
