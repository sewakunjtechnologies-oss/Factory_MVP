# Android Test Deployment Report

## 1. Deployment Objective

Prepare Factory Control for a limited paid Android owner-testing deployment using:

- Capacitor Android APK
- FastAPI backend
- SQLite on persistent cloud storage
- Persistent PDF/report storage
- Automated backup/restore scripts
- No database reset
- No May/June data deletion

## 2. Architecture Used

The existing architecture is preserved:

- FastAPI serves API and production React static assets.
- React + Vite remains the frontend.
- Capacitor wraps the built frontend for Android.
- SQLite remains the database for this test period.
- Fly.io is prepared as the recommended single-instance cloud host.
- Persistent volume path: `/app/data`
- Database path: `/app/data/factory.db`
- PDF path: `/app/data/generated_reports`

## 3. Repository Status

- Repository root: `/Users/lovishgrover/Downloads/factory_mvp_backend`
- Branch used: `android-testing-deployment`
- Uncommitted changes are present for deployment prep.
- Existing untracked `backups/` folder was preserved.

## 4. Backups Created

Backup directory:

```text
deployment_backups/20260625-031714/
```

Backed up:

- `data/factory.db`
- `backend/data/factory.db`
- `backend/generated_reports`
- `backend/uploads`
- redacted env snapshots
- Docker/Capacitor/Android config snapshots

Checksum file:

```text
deployment_backups/20260625-031714/SHA256SUMS.txt
```

Verification:

```text
SQLite backup verified: deployment_backups/20260625-031714/data/data_factory.db
```

Important active database counts:

| Table | Count |
|---|---:|
| users | 5 |
| purchase_orders | 37 |
| products | 37 |
| fabric_plans | 37 |
| fabric_mill_orders | 18 |
| dispatch_loads | 5 |
| alerts | 46 |
| reminders | 55 |
| report_requests | 36 |
| vehicles | 6 |

## 5. Security Changes

Completed:

- `.gitignore` now excludes env files, database files, deployment backups, generated reports, keystores, private keys, and private deployment secrets.
- Production secret generated into ignored local file:

```text
deployment_private/production-secrets.local
```

- Public registration can now be disabled with:

```text
ALLOW_PUBLIC_REGISTRATION=false
```

- Safe env templates created:
  - `.env.server.example`
  - `backend/.env.production.example`
  - `frontend/.env.production.example`
  - `frontend/.env.android.local.example`

Still requiring user action:

- Rotate Gemini API key if it was ever shared outside a private secret store.
- Set Fly secrets manually.
- Choose final owner testing password.
- Disable public registration in deployed env after owner account exists.

## 6. Backend Configuration

Completed:

- Docker runtime supports:

```text
DATABASE_URL=sqlite+aiosqlite:////app/data/factory.db
REPORT_OUTPUT_DIR=/app/data/generated_reports
UPLOAD_DIR=/app/data/uploads
PORT=${PORT:-8000}
```

- Startup now:
  - creates SQLite parent directory if missing
  - checks writable SQLite directory
  - creates report/upload directories
  - logs the active SQLite path without exposing secrets
  - avoids destructive seeding

- Scheduler can be disabled with:

```text
DISABLE_SCHEDULER=true
```

## 7. Persistent Storage

Fly.io volume prepared in config:

```toml
[[mounts]]
source = "factory_data"
destination = "/app/data"
```

The app is configured for one machine max/min while using SQLite.

## 8. Frontend API Configuration

Completed:

- Canonical API resolver remains in `frontend/src/api/axios.ts`.
- Development defaults to local backend only in dev mode.
- Production Android builds use `VITE_API_BASE_URL`.
- Cloud production URL currently set to:

```text
https://factory-control-owner-test.fly.dev
```

- Android API validation script created:

```text
frontend/scripts/check_android_api_url.mjs
```

Validation checks:

- missing `VITE_API_BASE_URL`
- localhost/127.0.0.1 backend URLs in cloud mode
- stale Cloudflare tunnel URLs
- duplicate `/api/v1/api/v1`

## 9. Capacitor Changes

Completed:

- `frontend/capacitor.config.ts` still uses:
  - appId: `com.factorymvp.control`
  - appName: `Factory Control`
  - webDir: `dist`
- Cloud builds disable mixed content by default.
- Local LAN builds can allow HTTP only with:

```text
VITE_ALLOW_LOCAL_HTTP=true
```

Native plugins remain present:

- `FactorySpeech`
- `FactoryNotifications`

Android permissions present:

- `INTERNET`
- `RECORD_AUDIO`
- `POST_NOTIFICATIONS`

## 10. Android Version Changes

Local Android project was updated for this build:

- previous `versionCode`: 1
- new `versionCode`: 2
- previous `versionName`: `1.0`
- new `versionName`: `1.0.0-test.1`
- applicationId unchanged: `com.factorymvp.control`

Note: the current repository ignores `frontend/android/`, so Android project changes are local unless the ignore policy is changed.

## 11. APK Builds

Debug APK built:

```text
deliverables/factory-control-owner-test-debug-1.0.0-test.1.apk
```

Size:

```text
4.2 MB
```

SHA-256:

```text
1d7a33030d23fd3941ac69afc8fac248262559ac2f08780c36faf762114b8544
```

Checksum file:

```text
deliverables/factory-control-owner-test-debug-1.0.0-test.1.apk.sha256
```

## 12. Backend Test Results

Command:

```bash
backend/.venv/bin/python -m pytest backend/tests -q
```

Result:

```text
47 passed, 4 skipped, 1 warning
```

Known assistant audit failure did not reproduce.

## 13. Frontend Build Results

Commands:

```bash
npm run lint
npm run build
ANDROID_API_MODE=cloud node scripts/check_android_api_url.mjs
```

Results:

- lint passed
- build passed
- Android API URL validation passed

## 13A. Docker Results

Commands:

```bash
docker build -t factory-control-owner-test:local .
docker run -d --name factory-control-smoke -p 18080:8000 -v <temp>:/app/data ...
curl -fsS http://127.0.0.1:18080/health
```

Results:

- Docker image build passed.
- Temporary container started with scratch SQLite volume.
- `/health` returned:

```json
{"app":"ok"}
```

## 14. Cloud Deployment Status

Status:

```text
BLOCKED — USER CREDENTIALS REQUIRED
BLOCKED — BILLING APPROVAL REQUIRED
```

Reason:

- Fly.io resource creation requires authenticated account and billing approval.
- Production secrets must be set by the owner/deployer.

Prepared files:

- `fly.toml`
- `scripts/deploy_fly.sh`
- `scripts/set_fly_secrets.sh.example`
- `MANUAL_CLOUD_DEPLOYMENT_STEPS.md`

## 15. Connected-Device Test Status

Status:

```text
BLOCKED — PHYSICAL DEVICE REQUIRED
```

`adb` is available, but no authorized Android device was connected.

No physical-device claims were made.

## 16. Voice Testing Status

Code paths remain present for:

- native Android speech recognition plugin
- native Android TTS plugin
- browser fallback

Status:

```text
BLOCKED — PHYSICAL DEVICE REQUIRED
```

Microphone, native TTS, stop speaking, and repeated voice question behavior must be tested on an actual Android device.

## 17. PDF Testing Status

Backend PDF generation remains authenticated and now uses configurable persistent output dir.

Status:

```text
PARTIALLY COMPLETED
```

Server-side PDF persistence path is prepared. Android PDF opening/sharing requires physical device QA.

## 18. Database Transfer Status

Status:

```text
BLOCKED — USER APPROVAL REQUIRED
```

No active database was uploaded to cloud.

Prepared file:

```text
DATABASE_CLOUD_TRANSFER.md
```

Verification helper:

```text
scripts/compare_db_counts.py
```

## 19. Remaining Manual Steps

1. Rotate Gemini API key if it has been exposed.
2. Create/login to Fly.io account.
3. Approve billing for one app and one 1GB volume.
4. Set Fly secrets.
5. Run Fly deployment script.
6. Transfer verified SQLite database to Fly volume only after approval.
7. Create secure owner test account.
8. Generate release keystore.
9. Wire keystore properties locally.
10. Build signed release APK.
11. Install APK on physical Android phone.
12. Complete `OWNER_ANDROID_QA_CHECKLIST.md`.

## 20. Rollback Procedure

Local rollback:

```bash
scripts/restore_sqlite.sh deployment_backups/20260625-031714/data/data_factory.db ./data/factory.db
```

Fly rollback:

1. Stop writes.
2. Restore previous `/app/data/factory.db`.
3. Restart app.
4. Run smoke test:

```bash
FACTORY_BASE_URL=https://factory-control-owner-test.fly.dev \
OWNER_EMAIL=... \
OWNER_PASSWORD=... \
scripts/smoke_test_deployment.py
```

## 21. Deliverable Paths

```text
deliverables/factory-control-owner-test-debug-1.0.0-test.1.apk
deliverables/factory-control-owner-test-debug-1.0.0-test.1.apk.sha256
deployment_backups/20260625-031714/
ANDROID_SIGNING_SETUP.md
BACKUP_AND_RESTORE.md
MANUAL_CLOUD_DEPLOYMENT_STEPS.md
DATABASE_CLOUD_TRANSFER.md
OWNER_ANDROID_QA_CHECKLIST.md
```

## 22. Exact Commands for Future Releases

Backend checks:

```bash
python3 -m compileall backend/app backend/tests backend/seed scripts
backend/.venv/bin/python -m pytest backend/tests -q
```

Frontend and Android:

```bash
cd frontend
npm run lint
npm run android:build:cloud
cd android
./gradlew assembleDebug
```

Docker:

```bash
docker build -t factory-control-owner-test:local .
```

Fly:

```bash
scripts/deploy_fly.sh factory-control-owner-test
```
