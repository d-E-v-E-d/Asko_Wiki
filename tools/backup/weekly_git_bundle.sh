#!/usr/bin/env bash
set -euo pipefail

# Disabled intentionally: a full Git bundle can contain historical content
# from sites/ or review/. Use a separate code-only repository before enabling
# Git-based bundle backups again.

LOG_DIR="${BUNDLE_ROOT:-/srv/arbeitsanweisung/backups/git-bundles}/logs"
LOG_FILE="${LOG_DIR}/weekly_git_bundle.log"

umask 027
mkdir -p "${LOG_DIR}"
echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') [INFO] Weekly Git bundle disabled: content must not be exported via Git." | tee -a "${LOG_FILE}"
exit 0
