#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "Usage: scripts/verify_sqlite_backup.sh path/to/backup.db" >&2
  exit 1
fi

if [[ -f "$BACKUP_FILE.sha256" ]]; then
  shasum -a 256 -c "$BACKUP_FILE.sha256"
fi

if ! command -v sqlite3 >/dev/null 2>&1; then
  echo "sqlite3 not found; checksum verified only." >&2
  exit 0
fi

integrity="$(sqlite3 "$BACKUP_FILE" 'PRAGMA integrity_check;')"
if [[ "$integrity" != "ok" ]]; then
  echo "Integrity check failed: $integrity" >&2
  exit 1
fi

echo "SQLite backup verified: $BACKUP_FILE"
