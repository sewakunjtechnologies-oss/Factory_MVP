# Factory MVP — Deployment runbook (Phases 5–8)

Phases 1–4 are done in code. The remaining steps need **your** accounts, your phone, and your decisions. They're written so you can copy-paste each block from top to bottom.

---

## What's already in place

| Thing | Path | State |
|---|---|---|
| FastAPI + SQLite single-container build | [Dockerfile](Dockerfile) | ✅ Builds; tested locally (`docker run` → 200 OK) |
| Frontend bundled into backend | `backend/static/` is part of the image | ✅ One URL serves UI + API |
| SQLite schema + data | `backend/data/factory.db` | ✅ 185 rows migrated from Postgres |
| WAL mode + foreign keys | [backend/app/core/database.py](backend/app/core/database.py) | ✅ Auto-applied on every connection |
| GUID type for cross-DB UUIDs | [backend/app/core/types.py](backend/app/core/types.py) | ✅ Works on Postgres + SQLite |
| Production image | `factory-mvp:local` (478 MB) | ✅ Locally verified |

---

## Phase 5 — Deploy to Fly.io (~45 min)

### 5.1 — Install Fly CLI and sign in

```bash
brew install flyctl
fly auth signup          # Browser opens. Use a real email. No credit card needed for free tier.
# Or, if you already have an account:
# fly auth login
```

Verify:
```bash
fly version
fly orgs list           # should show "personal" org at minimum
```

### 5.2 — Initialize the Fly app

```bash
cd /Users/lovishgrover/Downloads/factory_mvp_backend
fly launch --no-deploy
```

Answer the prompts:
- **App name**: `factory-control` *(or any globally unique name; you'll see it in your URL: `https://factory-control.fly.dev`)*
- **Region**: type `bom` for Mumbai (closest to India)
- **Postgres?** → **No**
- **Redis?** → **No**
- **Tigris (storage)?** → **No**
- **Deploy now?** → **No**

This creates [fly.toml](fly.toml).

### 5.3 — Replace `fly.toml` with this exact contents

```toml
app = "factory-control"        # MUST match the name you picked above
primary_region = "bom"

[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"
  DATABASE_URL = "sqlite+aiosqlite:////app/data/factory.db"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = "off"
  auto_start_machines = true
  min_machines_running = 1
  [http_service.concurrency]
    type = "requests"
    soft_limit = 200
    hard_limit = 250

[[vm]]
  cpu_kind = "shared"
  cpus = 1
  memory_mb = 512

[[mounts]]
  source = "factory_data"
  destination = "/app/data"

[[http_service.checks]]
  grace_period = "20s"
  interval = "30s"
  method = "GET"
  path = "/health"
  protocol = "http"
  timeout = "5s"
```

### 5.4 — Create the persistent disk

```bash
fly volumes create factory_data --size 3 --region bom --yes
# 3 GB is the free tier. Your SQLite file lives here; it survives every deploy.
```

### 5.5 — Set secrets

```bash
fly secrets set \
  GEMINI_API_KEY="<paste your real Gemini key>" \
  SECRET_KEY="$(openssl rand -hex 32)" \
  CORS_ORIGINS='["*"]'
```

> **Why `CORS_ORIGINS=["*"]`**: the React app + API now share an origin in normal browser use, so CORS is moot — but the Android APK uses `capacitor://` which is technically cross-origin. `*` keeps both working.

### 5.6 — Deploy

```bash
fly deploy
```

First deploy takes 4–6 min (uploads ~50 MB build context, builds in cloud, starts VM). Live tail:
```bash
fly logs                # ^C to detach; the app keeps running
```

When you see `Uvicorn running on http://0.0.0.0:8000`, you're live.

### 5.7 — Seed an owner user (production has an empty SQLite)

```bash
fly ssh console -C "/bin/sh -c 'python -c \"
import asyncio
from app.core.database import AsyncSessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.enums import UserRole

async def seed():
    async with AsyncSessionLocal() as db:
        u = User(
            full_name=\\\"Factory Owner\\\",
            email=\\\"owner@factory.com\\\",
            password_hash=hash_password(\\\"ChangeMe@2026\\\"),
            role=UserRole.owner,
            is_active=True,
        )
        db.add(u)
        await db.commit()

asyncio.run(seed())
print(\\\"seeded\\\")
\"'"
```

Save those credentials. **Have the owner change the password immediately on first login.**

### 5.8 — Verify everything

```bash
fly status              # shows the URL; should report "running" + 1 machine
open https://factory-control.fly.dev    # in browser
```

Steps to verify:
1. Login screen loads
2. Log in with `owner@factory.com` / `ChangeMe@2026`
3. Dashboard renders
4. Open Inventory → empty (production is fresh)
5. Open Assistant → ask "hello" → should reply

### 5.9 — (Optional) Copy your local SQLite to production

If you want production to start with all the data you migrated locally:

```bash
# Upload the local SQLite file directly to the Fly volume.
fly ssh sftp shell
# At the prompt:
put backend/data/factory.db /app/data/factory.db
quit
fly apps restart factory-control
```

> **Warning**: this overwrites the production DB. Only do this once, before owner starts using production.

### ✅ Phase 5 checkpoint

- [ ] `fly status` says `running`
- [ ] `https://factory-control.fly.dev` loads the login screen
- [ ] You can log in
- [ ] Assistant returns an answer

### 🔙 Rollback if something breaks

```bash
fly releases                          # list deploys
fly releases rollback <previous-id>   # back to the previous version in ~30 sec
```

---

## Phase 6 — Build APK + install on owner's phone (~30 min)

### 6.1 — Point the APK at the production URL

```bash
cd /Users/lovishgrover/Downloads/factory_mvp_backend/frontend
echo "VITE_API_BASE_URL=https://factory-control.fly.dev/api/v1" > .env.production
```

### 6.2 — Build the APK

```bash
npm run android:apk
```

First Gradle run takes 8–10 min (downloads Android SDK + dependencies). Subsequent: 30 sec.

The APK lands at:
```
frontend/android/app/build/outputs/apk/debug/app-debug.apk
```

If it fails, see **Phase 0 prerequisites** in the original plan (`ANDROID_HOME` + `JAVA_HOME`).

### 6.3 — Get the APK onto the owner's phone

Pick one:

**Easiest — Google Drive**:
1. Upload `app-debug.apk` to Google Drive on your Mac
2. On the phone, open Drive → tap the file → Download
3. Open the downloaded APK → install

**Fastest — USB cable + adb**:
```bash
adb devices                                      # phone must be in USB-debug mode
adb install -r android/app/build/outputs/apk/debug/app-debug.apk
```

**No-cable — email**: send the .apk as an email attachment to the owner; tap on phone to install.

### 6.4 — On the phone

1. Tap the APK → "Install from unknown sources" warning → **Allow once from Drive/Email** → **Install**
2. App icon appears in the drawer with the **F** mark
3. Open the app → login screen
4. Log in (`owner@factory.com` / `ChangeMe@2026`)
5. **Settings → change password** to something only the owner knows

### ✅ Phase 6 checkpoint

- [ ] APK installed
- [ ] Login works over **mobile data** (not just factory Wi-Fi) — confirms the cloud URL is reachable from anywhere
- [ ] Inventory page loads
- [ ] AI Assistant works on the phone

---

## Phase 7 — Daily backups (30 min)

### 7.1 — Create a Backblaze B2 bucket

```bash
brew install b2-tools
b2 account authorize        # browser opens; sign up for free B2 account
b2 bucket create factory-mvp-backups allPrivate
b2 key create --bucket factory-mvp-backups factory-backup-key writeFiles listFiles deleteFiles
# Save the keyID + applicationKey from the output — you need them next.
```

### 7.2 — Set B2 credentials as Fly secrets

```bash
fly secrets set \
  B2_APPLICATION_KEY_ID="<paste keyID>" \
  B2_APPLICATION_KEY="<paste applicationKey>" \
  B2_BUCKET="factory-mvp-backups"
```

### 7.3 — Add `b2` CLI to the production image

Edit [Dockerfile](Dockerfile), find this block:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sqlite3 \
    && rm -rf /var/lib/apt/lists/*
```

Change to:

```dockerfile
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl sqlite3 \
    && pip install --no-cache-dir b2 \
    && rm -rf /var/lib/apt/lists/*
```

### 7.4 — Add the backup job to APScheduler

Edit [backend/app/services/scheduler.py](backend/app/services/scheduler.py), add this function:

```python
async def _job_daily_backup() -> None:
    import os, subprocess, datetime
    try:
        ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        snap = f"/tmp/factory_{ts}.db"
        # Live snapshot — safe to run while DB is being written.
        subprocess.run(
            ["sqlite3", "/app/data/factory.db", f".backup '{snap}'"],
            check=True, timeout=120,
        )
        # Upload to B2 using env-var credentials.
        env = {
            **os.environ,
            "B2_APPLICATION_KEY_ID": os.environ["B2_APPLICATION_KEY_ID"],
            "B2_APPLICATION_KEY":    os.environ["B2_APPLICATION_KEY"],
        }
        subprocess.run(
            ["b2", "account", "authorize", "--key-id", env["B2_APPLICATION_KEY_ID"],
             "--application-key", env["B2_APPLICATION_KEY"]],
            check=True, timeout=30, env=env,
        )
        subprocess.run(
            ["b2", "file", "upload", os.environ["B2_BUCKET"], snap, f"factory_{ts}.db"],
            check=True, timeout=180, env=env,
        )
        os.remove(snap)
        logger.info("scheduler: backup uploaded as factory_%s.db", ts)
    except Exception:
        logger.exception("scheduler: backup failed")
```

And register it inside `start_scheduler()` next to the other jobs:

```python
scheduler.add_job(
    _job_daily_backup,
    CronTrigger(hour=20, minute=30),   # 02:00 IST (20:30 UTC previous day)
    id="daily_backup",
    replace_existing=True,
)
```

### 7.5 — Redeploy

```bash
fly deploy
```

### 7.6 — Run a manual restore drill (do this ONCE, today)

```bash
# Take a backup right now to verify the pipeline:
fly ssh console -C "python -c 'import asyncio; from app.services.scheduler import _job_daily_backup; asyncio.run(_job_daily_backup())'"
fly logs --since 1m | grep backup       # should see "uploaded as factory_..."

# Download a backup locally:
b2 ls factory-mvp-backups               # list available
b2 file download factory-mvp-backups factory_<timestamp>.db ./restored.db
sqlite3 restored.db "SELECT count(*) FROM users;"   # sanity check
```

### 7.7 — Add UptimeRobot (free) for "is it up?" alerts

1. Sign up at https://uptimerobot.com
2. New monitor → **Type: HTTPS** → **URL: `https://factory-control.fly.dev/health`** → 5-minute interval
3. Add your email + (optional) SMS as alert contacts

### ✅ Phase 7 checkpoint

- [ ] B2 bucket exists
- [ ] Manual backup succeeded; `b2 ls factory-mvp-backups` shows the file
- [ ] Restore drill done — you have `restored.db` locally and `SELECT` works
- [ ] UptimeRobot says "Up"

---

## Phase 8 — Day-to-day operations (reference)

### Deploy a code change

```bash
cd /Users/lovishgrover/Downloads/factory_mvp_backend
# Edit code...
git add -A && git commit -m "<what changed>"
fly deploy
# ~90 seconds. Zero-downtime rolling deploy.
```

### Watch live logs

```bash
fly logs                    # live tail; Ctrl-C to detach
fly logs --since 1h         # last hour, useful after a deploy
```

### SSH into the running container

```bash
fly ssh console
# You're now inside the production container as appuser.
sqlite3 /app/data/factory.db ".schema users"   # poke around
exit
```

### Roll back a bad deploy

```bash
fly releases                  # list deploys with IDs
fly releases rollback <id>    # back to that version in ~30 sec
```

### Check disk + memory

```bash
fly ssh console
df -h /app/data       # SQLite size, free space on Fly volume
free -m               # RAM usage
exit
```

### Update the APK (when needed)

The APK loads HTML/JS from production on every launch, so **frontend changes don't need a new APK**. Just `fly deploy` and the next time the owner opens the app it picks up the new bundle.

You only need to rebuild the APK if:
- You change the API base URL
- You change the app icon or manifest
- You bump Capacitor

### Scale up if usage grows

```bash
fly scale vm shared-cpu-2x --memory 1024   # bigger VM
fly volumes extend factory_data --size 10  # bigger disk
```

---

## What we built (concrete inventory)

| File | Why it exists |
|---|---|
| [Dockerfile](Dockerfile) (project root) | Single multi-stage image: Node builds React → Python serves API + static |
| [.dockerignore](.dockerignore) | Keeps build context small |
| [backend/app/core/types.py](backend/app/core/types.py) | `GUID` + `JSON_TEXT` — cross-DB column types |
| [backend/app/core/database.py](backend/app/core/database.py) | SQLite WAL mode + `foreign_keys=ON` + `create_all` helper |
| [backend/seed/migrate_pg_to_sqlite.py](backend/seed/migrate_pg_to_sqlite.py) | One-time data migration script |
| [backend/docker-compose.yml](backend/docker-compose.yml) | Dev runner (SQLite bind-mount + Postgres kept around just for the migration script) |
| [DEPLOY.md](DEPLOY.md) | This file |

### Files that became unnecessary

- `backend/app/core/redis.py` (deleted in Phase 1)
- `backend/requirements.txt` lines for `redis`, `psycopg`, `alembic` (removed)

### What you can safely delete now that SQLite is the source of truth

```bash
# After Phase 5 deploys and the production owner is happy:
docker rm -f factory_postgres        # local Postgres container
docker volume rm backend_postgres_data    # local Postgres data
rm backend/schema.sql                # old Postgres-specific schema
rm -rf backend/migrations/           # old Postgres migrations
# Don't remove anything in backend/seed/ — the migrate script is a useful audit trail.
```

You can also stop the `postgres:` service from `backend/docker-compose.yml` once everything's working.

---

## If something breaks

| Symptom | Likely cause | Fix |
|---|---|---|
| `fly deploy` hangs on push | Network. Big build context. | Check `.dockerignore` excludes `node_modules/dist/data/_archive` |
| App shows white screen on phone | `VITE_API_BASE_URL` not set / wrong | Rebuild APK with correct URL in `frontend/.env.production` |
| `fly logs` shows `ModuleNotFoundError` | Image build cached without a new dep | `fly deploy --no-cache` |
| AI Assistant returns 502 | Gemini overloaded | Wait 30s. Retry logic already handles transient 5xx. |
| SQLite "database is locked" | A long write while another writes | WAL mode is on; only happens if you have a multi-minute transaction. Inspect with `fly ssh console; sqlite3 /app/data/factory.db ".timeout 10000"` |
| Backup script fails | Missing B2 secrets | `fly secrets list` should show all 3 B2_* secrets |
| `fly ssh console` errors with "no public key" | Need to add SSH key once | `fly ssh issue --agent` then retry |

---

## Total status

**Phases 1–4: ✅ Done in code, tested locally. The factory app now runs as a single 478 MB container with no external DB, no Redis, no separate frontend host. Everything's on `localhost:8000` for you to test right now.**

**Phases 5–8: Ready to execute when you have 1–2 hours. Each step has copy-paste commands and a verification checkpoint.**
