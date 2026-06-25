# Database Cloud Transfer

Do not upload the active local database to cloud until deployment is confirmed, backup is verified, application writes are controlled, and the owner explicitly approves transfer.

## Safe Transfer Plan

1. Stop local application writes.
2. Create a final local backup:

```bash
DATABASE_FILE=./data/factory.db scripts/backup_sqlite.sh
```

3. Verify the backup:

```bash
scripts/verify_sqlite_backup.sh ./data/backups/factory-YYYYMMDD-HHMMSS.db
```

4. Stop the Fly machine or maintenance-window the app.
5. Upload the backup to `/app/data/factory.db` on the Fly volume.
6. Ensure ownership/permissions allow the app user to read/write.
7. Restart the Fly app.
8. Verify `/health`.
9. Compare counts:

```bash
scripts/compare_db_counts.py ./data/factory.db downloaded-cloud-copy.db
```

10. Verify May and June records in the dashboard and PO list.

## Rollback

1. Stop app writes.
2. Restore previous `/app/data/factory.db` backup.
3. Restart app.
4. Run smoke tests.

## Important Tables to Compare

- users
- purchase_orders
- products
- fabric_plans
- fabric_mill_orders
- dispatch_loads
- alerts
- reminders
- report_requests
- vehicles
