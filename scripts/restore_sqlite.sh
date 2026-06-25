#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"
DB_PATH="${DATABASE_FILE:-${2:-./data/factory.db}}"

if [[ -z "$BACKUP_FILE" || ! -f "$BACKUP_FILE" ]]; then
  echo "Usage: scripts/restore_sqlite.sh path/to/backup.db [database-path]" >&2
  exit 1
fi

scripts/verify_sqlite_backup.sh "$BACKUP_FILE"

echo "Target database: $DB_PATH"
echo "This will replace the target database. Stop the application before continuing."
read -r -p "Type RESTORE to continue: " answer
if [[ "$answer" != "RESTORE" ]]; then
  echo "Restore cancelled."
  exit 1
fi

mkdir -p "$(dirname "$DB_PATH")"
if [[ -f "$DB_PATH" ]]; then
  pre_restore="${DB_PATH}.pre-restore-$(date +%Y%m%d-%H%M%S)"
  sqlite3 "$DB_PATH" ".backup '$pre_restore'"
  shasum -a 256 "$pre_restore" > "$pre_restore.sha256"
  echo "Pre-restore backup: $pre_restore"
fi

cp "$BACKUP_FILE" "$DB_PATH"
sqlite3 "$DB_PATH" 'PRAGMA integrity_check;'
echo "Restore complete. Restart the application and verify /health."
