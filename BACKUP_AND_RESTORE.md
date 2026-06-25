# Backup and Restore

## Local Backup

Use SQLite online backup. Do not copy a live SQLite database directly when WAL mode may be active.

```bash
DATABASE_FILE=./data/factory.db scripts/backup_sqlite.sh
```

Backups are written to:

```text
./data/backups/
```

Each backup includes a SHA-256 checksum.

## Verify Backup

```bash
scripts/verify_sqlite_backup.sh ./data/backups/factory-YYYYMMDD-HHMMSS.db
```

This checks the checksum when present and runs `PRAGMA integrity_check`.

## Restore Backup

Stop application writes first.

```bash
scripts/restore_sqlite.sh ./data/backups/factory-YYYYMMDD-HHMMSS.db ./data/factory.db
```

The restore script requires typing `RESTORE` and creates a pre-restore backup.

## Fly Volume Backup

Recommended approach:

1. SSH into the Fly machine.
2. Run `scripts/backup_sqlite.sh` inside the app image, or run `sqlite3 /app/data/factory.db ".backup '/app/data/backups/factory-...db'"`.
3. Download the backup using `fly sftp` or `fly ssh sftp`.
4. Verify the checksum locally.

## External Backup Recommendation

For paid testing, keep at least one local backup and one off-machine copy after each demo day. Do not configure a paid backup service until the owner approves the cost.

## Retention Policy

Default retention is 14 days:

```bash
BACKUP_RETENTION_DAYS=14 scripts/backup_sqlite.sh
```

## Restore Test

Before relying on cloud backups, restore one backup into a temporary database path and run:

```bash
scripts/verify_sqlite_backup.sh restored.db
scripts/compare_db_counts.py original.db restored.db
```
