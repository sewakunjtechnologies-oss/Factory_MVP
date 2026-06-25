#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${DATABASE_FILE:-${1:-./data/factory.db}}"
BACKUP_ROOT="${BACKUP_ROOT:-./data/backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "Database file not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_ROOT"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_file="$BACKUP_ROOT/factory-$timestamp.db"

if command -v sqlite3 >/dev/null 2>&1; then
  sqlite3 "$DB_PATH" ".backup '$backup_file'"
  integrity="$(sqlite3 "$backup_file" 'PRAGMA integrity_check;')"
  if [[ "$integrity" != "ok" ]]; then
    echo "Backup integrity check failed: $integrity" >&2
    exit 1
  fi
else
  echo "sqlite3 not found; refusing unsafe live copy." >&2
  exit 1
fi

shasum -a 256 "$backup_file" > "$backup_file.sha256"
find "$BACKUP_ROOT" -name 'factory-*.db' -mtime +"$RETENTION_DAYS" -print -delete
find "$BACKUP_ROOT" -name 'factory-*.db.sha256' -mtime +"$RETENTION_DAYS" -print -delete

echo "Backup created: $backup_file"
echo "Checksum: $backup_file.sha256"
