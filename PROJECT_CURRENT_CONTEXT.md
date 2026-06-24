# Factory MVP Current Context

Generated on 2026-06-19 from the local repository at `/Users/lovishgrover/Downloads/factory_mvp_backend`.

## 1. Executive Summary

Factory MVP is currently a FastAPI + React factory execution system for textile PO tracking, fabric planning, mill follow-up, packing, dispatch, PDF reports, and a Gemini-backed owner assistant. The local Docker backend on port `8000` is healthy and serving API routes. The frontend builds successfully and is configured to call `http://127.0.0.1:8000`.

The current local database is June-demo oriented: it contains exactly 37 `JUNE-*` purchase orders, 37 product/fabric lines, 37 fabric plans, 18 mill orders, 53 packing material rows, 46 alerts, 55 reminders, 5 dispatch loads, 6 vehicles, and 35 PDF report requests. Older demo records such as `PO-2026-001` and `DEMO-PO-*` are not present in the active Docker database.

The project is close to a limited Android testing deployment because it already has a Capacitor Android project, PWA manifest/service worker, native Android speech/notification plugins, Docker packaging, and APK deliverables. It is not production-ready yet: role permissions are collapsed to owner/manager, tests are not fully passing, SQLite backup/hosting strategy is not active, secrets exist in local env files, and the Android bundle must be regenerated after recent frontend changes.

## 2. Current Project Structure

- Root: `Dockerfile`, `docker-compose.yml`, `.env`, `.env.server.example`, `.dockerignore`, `DEPLOY.md`, `SERVER_LAPTOP_SETUP.md`, `README.md`, `deliverables/`, `data/`.
- Backend: `backend/app`, `backend/seed`, `backend/tests`, `backend/migrations`, `backend/generated_reports`, `backend/data`, `backend/requirements.txt`, `backend/Dockerfile`, `backend/docker-compose.yml`.
- Frontend: `frontend/src`, `frontend/public`, `frontend/dist`, `frontend/android`, `frontend/package.json`, `frontend/capacitor.config.ts`, `frontend/.env`, `frontend/.env.production`.
- Android: `frontend/android/app/src/main`, custom Java plugins in `frontend/android/app/src/main/java/com/factorymvp/control`.
- Database files: SQLite DBs exist under `data/factory.db` and `backend/data/factory.db`. The active Docker DB path is `/app/data/factory.db`, mounted from root `./data`.
- Reports: local PDF files are in `backend/generated_reports`.
- Migrations: SQL migration files exist in `backend/migrations`; `backend/alembic/versions` exists but the active DB has no `alembic_version` table.

## 3. Technology Stack

Backend:
- Framework: FastAPI `0.115.0`.
- Runtime: Python 3.11 in Docker; local system `python3` is 3.8 and not dependency-complete.
- ORM: SQLAlchemy `2.0.35` async.
- Database: SQLite via `aiosqlite` for current app/container; old Postgres migration artifacts remain.
- Auth: JWT bearer tokens using `python-jose`, password hashing via `passlib`/bcrypt.
- Scheduler: in-process APScheduler jobs for reminders, alert generation, and shortage checks.
- PDF: ReportLab, stored on local disk.
- AI provider: Google Gemini via `google-genai`.
- File/image storage: local filesystem/static file serving; no object storage integrated in code.
- API base path: `/api/v1`.

Frontend:
- Framework: React `19.2.5`.
- Language/build: TypeScript `6.0.x`, Vite `8.0.10`.
- Styling: Tailwind CSS.
- API/query: Axios plus TanStack Query.
- Routing: React Router `7.14.2`.
- State: Zustand for auth/session and assistant turns.
- Voice input: browser `SpeechRecognition`/`webkitSpeechRecognition` fallback plus custom Capacitor `FactorySpeech` plugin.
- Voice output: browser `speechSynthesis` plus custom Capacitor `FactorySpeech` text-to-speech.
- PWA: manifest + service worker are present.
- Android: Capacitor Android project is present.

Infrastructure:
- Current local run: Docker single-container app on `127.0.0.1:8000` with SQLite bind mount.
- Deployment docs recommend Fly.io, SQLite volume, optional Backblaze B2 backups, UptimeRobot, and APK handoff.
- Docker Compose also still starts unrelated/stale services on this machine, including Redis and Postgres containers.

## 4. Current Features and Status

| Module | Status | Evidence | Notes |
|---|---|---|---|
| Authentication and users | Working | Login smoke with `niraj@factory.com` returned token; auth-protected APIs returned 200. | Register route exists. Demo credentials are present in local DB/docs. |
| Roles and permissions | Partially Working | `security.py` collapses legacy roles to owner/manager aliases. | Fine for owner demo, not true role-based factory workflow. |
| Purchase orders | Working | 37 POs in DB; `/api/v1/purchase-orders` returned 200. | CRUD routes exist. Current data is June-only. |
| Product categories | Partially Working | `products` and `product_fabric_lines` tables/routes exist. | No separate normalized category table found. |
| Design library | Present but Untested | `fabric_designs` model/routes exist. | Not smoke-tested in this audit. |
| Fabric planning | Working | 37 `fabric_plans`; calculation service exists; dashboard uses shortage meters. | Separate `fabric_shortages` table does not exist; shortage is plan/requirement based. |
| Fabric inventory | Working | CRUD routes exist under `/fabric-inventory`. | Not individually smoke-tested in this audit. |
| Fabric shortage | Working | Plan shortage fields, mill requirements, reminders, reports, assistant paths exist. | Backend test failure shows one assistant shortage query regression in isolated test dataset. |
| Mill orders | Working | 18 `fabric_mill_orders`; `/fabric-operations/mill-orders` returned 200. | Split/cancel/shift/delivery lot routes exist. |
| Mill invoice/order generation | Partially Working | Mill order records include invoice-related fields; reports and list route exist. | Not a formal accounting invoice subsystem. |
| Fabric verification | Partially Working | Receipt verification routes/models exist. | Not smoke-tested end-to-end. |
| Fabric allocation to cutting | Partially Working | `/fabric-operations/issue-to-cutting` and model exist. | Role granularity not enforced beyond owner/manager. |
| Cutting verification | Partially Working | Cutting analysis route/model exists. | Not fully tested in current audit. |
| Wastage tracking | Partially Working | Cutting analysis and mill wastage history models/routes exist. | Test coverage exists, but full suite has one failure unrelated to wastage. |
| Stitching allocation | Partially Working | Generic stage allocation/progress supports stitching. | No dedicated stitching mobile workflow proved. |
| Stitching verification | Partially Working | Generic stage progress and quality failure models exist. | Full rework loop not verified. |
| Repair and alteration | Partially Working | Stage summaries and dispatch shortfall handling include repair/alter quantities. | Not full closed-loop workflow. |
| Packing allocation | Partially Working | Packing plan/output routes exist. | Needs more functional verification on phone. |
| Packing material inventory | Working | `/packing-materials` returned 200; 53 rows in DB; CRUD routes exist. | Recent page exists but is untracked in git. |
| Packing capacity | Partially Working | Packing analysis/plan services exist. | Capacity assumptions are app-specific, not fully validated in audit. |
| Dispatch | Working | Dispatch routes exist; 5 dispatch loads in DB; dispatch planner smoke returned 200 with a real vehicle. | Planner returned empty load for selected priorities due no eligible bale rows. |
| Partial dispatch | Working | Active DB shows `JUNE-004` shipped `3380`, `JUNE-005` shipped `9000`. | Dashboard/API smoke passed. |
| Dispatch costing | Partially Working | Dispatch models/services include cost fields and CBM/vehicle planning. | Not all costing modes smoke-tested. |
| Alerts | Working | 46 alerts; `/alerts` route exists; dashboard uses alert data. | Generation job exists. |
| Reminders | Working | 55 reminders; route and scheduler jobs exist. | Escalation route/job exists. |
| Notifications | Partially Working | Notification table/service/routes and Android notification plugin exist. | No push service; in-app/native scheduled notification only. |
| Dashboard | Working | `/api/v1/dashboard/owner` returned 200 with auth. | Frontend build includes dashboard page. |
| AI assistant | Partially Working | `/api/v1/voice/ask` returned 200 for owner question; deterministic + Gemini fallback exists. | Full backend test suite has one assistant audit failure; Gemini key/config can still fail for fallback questions. |
| Voice input | Present but Untested | Hold-to-speak browser and Capacitor logic exists. | Not manually tested in browser/phone during this audit. |
| Voice output | Present but Untested | `speechSynthesis` and native TTS code exist. | Not audio-tested in this audit. |
| PDF generation | Working | 35 report request rows; 93 PDF files on disk; report list route returned 200. | New PDF generation was not triggered to avoid data/file changes. |
| Demo seed data | Partially Working | Multiple seed scripts exist. Current active DB has 37 June POs only. | Did not run seed scripts to avoid resetting data. |
| Testing | Partially Working | Frontend lint/build pass; backend compile passes. | Backend tests: 37 passed, 4 skipped, 1 failed. |
| Mobile responsiveness | Present but Untested | Tailwind responsive layouts and mobile routes exist. | Needs phone QA. |
| Android packaging/deployment | Partially Working | Capacitor project and APK deliverables exist. | Must rerun `npm run android:sync`/APK build after latest frontend changes. |

## 5. Backend Status

Entry point: `backend/app/main.py`.

The backend registers 123 API routes under `/api/v1` and 131 total FastAPI routes including docs/static/health. The active routes include auth, products, product fabric lines, PO CRUD, fabric designs, fabric inventory, fabric receipts, fabric operations, contractors, capacity, stages, quality, packing, packing materials, dispatch, vehicles, notifications, alerts, reminders, PDF reports, dashboard, and voice assistant.

Startup behavior:
- Calls `create_all_tables()`.
- Ensures packing material schema.
- Runs operational backfill.
- Starts APScheduler unless disabled by env/test.

Database:
- Current Docker app uses SQLite at `/app/data/factory.db`.
- `create_all` is the main schema provisioning path.
- SQL migration files exist, but active SQLite DB has no `alembic_version`.
- WAL, foreign keys, and busy timeout are enabled for SQLite.

Authentication:
- JWT token auth works.
- Login smoke passed with current owner user.
- Protected APIs correctly return 401 without a token.

Backend blockers:
- Full backend test suite currently fails one assistant audit test.
- Local system `python3` is not a valid test/runtime environment because it lacks dependencies; use `backend/.venv/bin/python` or Docker.
- Role gates are not production granular.
- SQLite is acceptable for testing but needs backup and concurrency expectations before production.

## 6. Frontend Status

Entry point: `frontend/src/App.tsx`.

Routes/pages:
- `/login`, `/register`, `/dashboard`, `/pos`, `/pos/create`, `/po/:id`, `/inventory`, `/fabric`, `/fabric-ops`, `/allocation`, `/production`, `/packing`, `/packing-materials`, `/contractors`, `/dispatch`, `/reminders`, `/alerts`, `/assistant`, `/ai-import`.

API configuration:
- `frontend/src/api/axios.ts` defaults to `http://127.0.0.1:8000` and appends `/api/v1`.
- `frontend/.env` and `frontend/.env.production` point to local port `8000`.
- Previous Cloudflare URL is not the frontend API base anymore.

Build:
- `npm run lint` passed.
- `npm run build` passed.
- No explicit `typecheck` or `test` script exists; build includes `tsc -b`.

Frontend blockers:
- `frontend/android` assets are older than the latest `frontend/dist` until Capacitor sync is rerun.
- Several frontend changes are uncommitted/untracked.
- Voice input/output needs actual browser and Android device QA.

## 7. AI Assistant Status

Current assistant route: `POST /api/v1/voice/ask`.

Request shape:

```json
{ "message": "What should I show the owner today?" }
```

Response shape:

```json
{ "answer": "text", "artifacts": [] }
```

How it works:
- The route requires owner or manager.
- It first calls deterministic `answer_factory_question()` with live DB data.
- If no deterministic answer exists, it builds a compact DB snapshot and sends it to Gemini.
- PDF artifacts are collected via a per-request artifact sink.
- Write actions detected by deterministic parser are previewed and require confirmation before execution.

Supported/observed capabilities:
- June PO summaries.
- Fabric readiness/shortage questions.
- Mill orders/invoices.
- Packing materials.
- Dispatch and truck planning context.
- Voice update previews for dispatch, fabric ordered/received, PO status, product/PO field updates, and packing material updates.
- PDF generation through tools/report service.

Known AI issues:
- Backend tests show a regression: “Which June POs have fabric shortage?” returned the packing-material fallback in one isolated test DB, causing test failure.
- Gemini fallback can still return 502/503/400-style errors if key/quota/model access fails.
- `/voice/ask` allows manager as well as owner; earlier owner-only business rule is not strictly enforced.

## 8. Voice Input and Output Status

Current frontend flow:
- Manual hold-to-speak button in `AssistantPage`.
- No wake-word primary flow.
- Browser path uses `SpeechRecognition`/`webkitSpeechRecognition`.
- Native Android path uses custom Capacitor plugin `FactorySpeech`.
- The React hook sends final transcript to `/voice/ask`, appends response, then speaks the answer.

Voice output:
- Browser path uses `window.speechSynthesis`.
- Text is chunked into roughly 220-character chunks.
- Native Android path uses `TextToSpeech`.
- The current UI does not expose a separate “speak responses” toggle on `AssistantPage`; hold-to-speak answers are spoken by the hook.

Status:
- Present but not audio-tested in this audit.
- Browser microphone and TTS behavior can vary by Chrome permissions, OS audio, and Android WebView.
- Native plugins are manually registered in `MainActivity`, and Android manifest includes `RECORD_AUDIO` and `POST_NOTIFICATIONS`.

## 9. PDF Report Status

PDF library: ReportLab.

Endpoints:
- `POST /api/v1/reports/pdf/generate`
- `GET /api/v1/reports/pdf`
- `GET /api/v1/reports/pdf/{report_id}`
- `GET /api/v1/reports/pdf/{report_id}/download`

Implemented report types include:
- Running/active/delayed POs.
- PO status and PO stage progress.
- Fabric shortage, stock, verification pending.
- Mill orders and late mill deliveries.
- Contractor delay/performance.
- Daily production and stage progress.
- QC failures.
- Packing risk/capacity.
- Pending dispatch, June dispatch, dispatch-ready, dispatch cost.
- Alerts, reminders, daily factory summary, urgent actions, owner review.
- Mill split, partial mill delivery, fabric verification/mismatch/allocation, cutting wastage, contractor partial return, stitching verification, repair/rework, dispatch documentation/exception, buyer return, role pending tasks, escalated reminders.

Storage:
- Local directory `backend/generated_reports`.
- 93 files existed at audit time.
- Active DB had 35 report requests: 32 completed, 3 failed.

Android/PWA notes:
- Downloads are JWT-protected; frontend fetches PDF blobs with Axios instead of plain links.
- Local filesystem reports persist only if the deployment volume persists.
- Android WebView/PWA PDF opening needs device testing.

## 10. Database and Seed Data Status

Active Docker database counts:

| Table/Area | Count |
|---|---:|
| users | 5 |
| purchase_orders | 37 |
| products | 37 |
| product_fabric_lines | 37 |
| fabric_plans | 37 |
| fabric_mill_orders | 18 |
| dispatch_loads | 5 |
| packing_material_inventory | 53 |
| alerts | 46 |
| reminders | 55 |
| report_requests | 35 |
| vehicles | 6 |

Current demo records:
- `JUNE-*` POs: 37.
- `DEMO-PO-*`: 0.
- `PO-2026-001`: 0.
- `JUNE-004` dispatched quantity: 3380.
- `JUNE-005` dispatched quantity: 9000.

Seed scripts present:
- `backend/seed/seed_june_pdf_status.py`
- `backend/seed/seed_sample_pos.py`
- `backend/seed/seed_fabric_designs.py`
- `backend/seed/backfill_packing_materials.py`
- `backend/seed/apply_owner_june_updates.py`
- `backend/seed/repair_june_po_operational_data.py`
- `backend/seed/migrate_pg_to_sqlite.py`
- `backend/seed/run_assistant_question_audit.py`

No seed/reset script was run during this audit.

## 11. Tests and Verification Results

Commands run:

| Command | Result | Notes |
|---|---|---|
| `python3 -m compileall backend/app` | Passed | Syntax compile only; local Python lacks all deps. |
| `docker exec factory_mvp_server python -m compileall app` | Passed | Deployment-like container environment. |
| `backend/.venv/bin/python -m compileall backend/tests` | Passed | Test files compile. |
| `backend/.venv/bin/python -m pytest backend/tests -q` | Failed | 1 failed, 37 passed, 4 skipped. |
| `cd frontend && npm ls --depth=0` | Passed | Dependencies installed. |
| `cd frontend && npm run lint` | Passed | ESLint clean. |
| `cd frontend && npm run build` | Passed | TypeScript build + Vite build passed. |
| `cd frontend && npm run typecheck --if-present` | No-op | No script configured. |
| `cd frontend && npm test --if-present` | No-op | No test script configured. |
| `curl http://127.0.0.1:8000/health` | Passed | Returned `{"app":"ok"}`. |
| Authenticated API smoke checks | Passed | Dashboard, POs, packing materials, vehicles, reports, mill orders, assistant. |

Failed backend test:

```text
backend/tests/test_factory_assistant_audit.py::test_assistant_answers_shortage_stage_and_contractor_without_hallucination
Expected "109-SHORT-FLORA-JUNE" in answer, but assistant returned:
"No packing material rows found. Use the Packing Materials page and click Generate June materials."
```

Other command issue:
- A host import route-count check with system `python3` failed because the system Python is 3.8 and missing `aiosqlite`. This is an environment issue, not a container app failure. Use `backend/.venv/bin/python` or Docker.

## 12. Current Bugs and Blockers

Critical:
- Secrets are present in local env files; must not be committed or shared.
- No verified backup/restore setup is active for the SQLite production path.

High:
- Backend tests are not fully green due an AI assistant audit failure.
- Role permissions are not the requested full textile role matrix; legacy role dependencies map to owner/manager.
- Android APK/bundle must be regenerated after current frontend changes.
- Current local Docker Compose still includes a Cloudflare CORS regex default, even though frontend is local-port based.

Medium:
- Full voice input/output was not manually tested during this audit.
- PDF generation was not freshly triggered in this audit to avoid creating rows/files; existing report list/files are present.
- Frontend test suite is not configured.
- Multiple stale containers are running on the machine, including an unhealthy `backend-api:latest` container and Redis/Postgres containers unrelated to the current SQLite app.

Low:
- Generated reports are local files and not stored in object storage.
- Deployment docs mention Fly.io and Backblaze, but those are not currently wired as active deployed services.

## 13. Android Deployment Readiness

Current type: responsive React web app with PWA support and a Capacitor Android wrapper.

PWA readiness:
- Manifest exists.
- Service worker exists.
- Offline support is app-shell only; API data is always network-first.

Capacitor readiness:
- `frontend/android` exists.
- `capacitor.config.ts` exists.
- Custom native speech and notification plugins exist.
- Android manifest has internet, microphone, and notification permissions.
- `allowMixedContent` and cleartext traffic are enabled for local/testing HTTP.

Not ready yet:
- Need to run `npm run android:sync` after latest frontend build.
- Need to choose API host reachable from the Android phone.
- Need device QA for login, voice, PDF download, and dispatch/packing pages.

## 14. Available Android Deployment Options

| Option | Current Support | Work Required | Risks/Limitations | Estimated Effort |
|---|---|---|---|---|
| PWA installed from Chrome | Supported | Host app over HTTPS or use local LAN for testing; verify manifest/install prompt. | Browser speech recognition/TTS varies; no Play Store presence; limited native notifications. | Low |
| Trusted Web Activity | Not configured | Create Android TWA shell and host HTTPS web app with asset links. | Requires HTTPS domain and digital asset links; more setup than needed for quick test. | Medium |
| Capacitor Android wrapper | Supported | Rebuild/sync Android, set API URL, test on phone, produce APK. | Requires Android SDK/Gradle; local IP/HTTP can break outside same network. | Low to Medium |
| Simple Android WebView wrapper | Not needed | Build separate native shell. | Duplicates Capacitor capability; more custom maintenance. | Medium |
| Full native rebuild | Not applicable | Rebuild app in native Android/React Native. | Too much work; high cost; unnecessary for MVP testing. | High |

## 15. Recommended Testing Deployment Path

Technical recommendation for a short owner testing period:

Use the existing Capacitor Android wrapper with a single reachable backend URL. For local factory-floor testing, point the APK at the server laptop’s LAN IP and keep the backend Docker container on port `8000`. For off-network testing, use a real HTTPS host or a controlled tunnel. This is the fastest path because the Android project and native speech plugin already exist.

This is a technical recommendation only, not a pricing decision.

## 16. Required Hosting and Third-Party Services

| Service | Purpose | Free/Paid | Current Use | Credentials Configured | Required for Android Testing |
|---|---|---|---|---|---|
| Local Docker/server laptop | Run FastAPI + SQLite + static frontend | Free hardware-dependent | Active local backend on port 8000 | Local env present | Yes for local testing |
| SQLite volume/bind mount | Store app data | Free | Active via `./data:/app/data` | Not applicable | Yes |
| Gemini API | AI fallback answers | Paid/free quota depending Google account | Configured in env; deterministic answers work without it for many questions | Key present locally | Required for broad AI fallback, not all deterministic demo answers |
| Fly.io | Cloud hosting option | Free/paid depending usage | Documented only | Not active in repo | Optional |
| Backblaze B2 | Backup option | Free/paid depending storage | Documented only | Not active | Optional but recommended before production |
| UptimeRobot | Uptime alerts | Free/paid | Documented only | Not active | Optional |
| Google Play Developer | Play Store distribution | Paid one-time account | Not configured | Not present | Not required for sideload test APK |
| Android SDK/Gradle | APK build | Free | Android project present | Local machine dependent | Required to build APK |

No Cloudinary, Firebase, Redis-backed runtime, Deepgram, OpenAI, Vercel, Render, or object storage integration was found as active application code.

## 17. Security and Production Risks

| Risk | Severity | Evidence | Recommendation |
|---|---|---|---|
| Local Gemini API key present in env files | Critical | `.env`/`backend/.env` contain AI key configuration. | Rotate if exposed; keep only in deployment secrets. |
| Weak/default secrets in examples/config | High | Docker compose/default docs include fallback secret strings. | Require strong `SECRET_KEY` in deployment. |
| Demo credentials documented | High | Setup docs and seeds include demo emails/passwords. | Change credentials before owner testing outside local LAN. |
| Permissive CORS in Docker compose | Medium | `CORS_ORIGINS=["*"]`, Cloudflare regex default remains. | Restrict to test app origin/API host. |
| Cleartext Android traffic allowed | Medium | Android manifest and Capacitor config allow HTTP. | Accept only for local test; switch to HTTPS for wider testing. |
| Role model too broad | High | Legacy role gates alias to owner/manager. | Add real roles before multi-user production. |
| SQLite backup not active | High | Backup plan is documentation-only. | Implement and test backup/restore before production use. |
| Local PDF files | Medium | Generated PDFs stored under local directory. | Mount persistent volume or object storage. |
| Register route public | Medium | `/auth/register` exists. | Disable or restrict registration before production. |
| Stale containers on host | Low | Multiple unrelated containers running. | Clean server laptop before owner testing. |

## 18. Work Required Before Android Testing

1. Decide testing topology: same-Wi-Fi LAN server laptop, public HTTPS host, or tunnel.
2. Set frontend API base URL to the chosen backend URL.
3. Rebuild frontend and run `npm run android:sync`.
4. Build a fresh debug APK.
5. Confirm login on the Android phone.
6. Test dashboard, PO detail, fabric/fabric lines, packing materials, dispatch planner, assistant text, hold-to-speak, voice output, and PDF download.
7. Clean or stop stale containers on the server laptop.
8. Move secrets out of files into environment/secret manager for anything beyond a local test.
9. Fix or accept the known failing backend AI test before presenting AI as fully reliable.

## 19. Work Required Before Full Production

1. Implement real role-based access beyond owner/manager.
2. Add reliable backup/restore for SQLite or migrate to managed Postgres.
3. Lock down CORS, registration, secrets, and demo credentials.
4. Add frontend automated tests for critical pages and assistant loop.
5. Make backend tests fully green.
6. Add production file/object storage for reports and uploaded designs.
7. Validate full workflow on real factory data: PO creation, fabric calculation, mill order, verification, packing material, dispatch, PDF, AI update confirmation.
8. Add monitoring/logging/alerting.
9. Test Android PDF downloads, microphone permissions, native speech, notifications, and file uploads on target devices.

## 20. Exact Local Run Commands

Backend Docker:

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

Backend local virtualenv:

```bash
cd /Users/lovishgrover/Downloads/factory_mvp_backend
backend/.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

Frontend dev:

```bash
cd /Users/lovishgrover/Downloads/factory_mvp_backend/frontend
npm install
npm run dev -- --host 0.0.0.0
```

Verification:

```bash
python3 -m compileall backend/app
docker exec factory_mvp_server python -m compileall app
backend/.venv/bin/python -m compileall backend/tests
backend/.venv/bin/python -m pytest backend/tests -q
cd frontend && npm run lint
cd frontend && npm run build
```

Android:

```bash
cd /Users/lovishgrover/Downloads/factory_mvp_backend/frontend
npm run android:sync
npm run android:apk
```

## 21. Exact Deployment-Related Files

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `.env`
- `.env.server.example`
- `DEPLOY.md`
- `SERVER_LAPTOP_SETUP.md`
- `backend/Dockerfile`
- `backend/docker-compose.yml`
- `backend/.env`
- `backend/.env.docker.example`
- `backend/app/main.py`
- `backend/app/core/config.py`
- `backend/app/core/database.py`
- `frontend/.env`
- `frontend/.env.production`
- `frontend/capacitor.config.ts`
- `frontend/public/manifest.webmanifest`
- `frontend/public/sw.js`
- `frontend/android/app/src/main/AndroidManifest.xml`
- `frontend/android/app/src/main/java/com/factorymvp/control/FactorySpeechPlugin.java`
- `frontend/android/app/src/main/java/com/factorymvp/control/FactoryNotificationsPlugin.java`
- `frontend/android/app/src/main/java/com/factorymvp/control/MainActivity.java`
- `deliverables/factory-control-owner-demo-2026-06-02.apk`
- `deliverables/factory-control-cloudflare-2026-06-02.apk`

## 22. Open Questions and Missing Information

1. Should Android testing be same-Wi-Fi local only, or should the owner access it from outside the factory network?
2. Which backend URL should the APK use: LAN IP, public domain, Fly.io, or tunnel?
3. Should public registration remain enabled during owner testing?
4. Should Gemini fallback be required for the paid test, or are deterministic factory answers enough?
5. Are current 37 June POs final for testing, or should seed scripts be disabled to prevent accidental reset?
6. Which user accounts should exist on the owner’s test phone?
7. Should SQLite remain the production DB, or is managed Postgres preferred for long-term use?
8. Should generated PDFs be retained permanently, and if yes, where should they be stored?
9. Are role-specific staff users needed for this Android testing period, or owner-only is enough?
10. Should Play Store/internal testing be used, or is APK sideloading acceptable for the paid test?
