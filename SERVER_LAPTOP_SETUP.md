# Factory MVP Server Laptop Setup

Use this when moving the project to another laptop for a cleaner testing period.

## 1. Install prerequisites

Install these on the server laptop:

- Git
- Docker Desktop
- Optional: Node.js 22 and Python 3.11 if you also want to run without Docker

## 2. Clone the repo

```bash
git clone https://github.com/sewakunjtechnologies-oss/Factory_MVP.git
cd Factory_MVP
```

## 3. Configure environment

```bash
cp .env.server.example .env
```

Edit `.env` and set:

```text
GEMINI_API_KEY=<your Gemini API key>
SECRET_KEY=<a long random secret>
```

Generate a secret if needed:

```bash
openssl rand -hex 32
```

## 4. Build and start the server

```bash
mkdir -p data backend/generated_reports
docker compose up --build -d
```

Open:

```text
http://127.0.0.1:8000
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## 5. Seed the June demo data

This creates the current 37 June POs, vehicle length options, users, fabric, mill orders, dispatch data, and dashboard-ready records.

```bash
docker compose exec factory-mvp python seed/seed_june_pdf_status.py
```

Login credentials:

```text
Owner:
email: owner@factorydemo.com
password: Owner@123

Manager:
email: manager@factorydemo.com
password: Manager@123
```

## 6. Access from another device on the same Wi-Fi

Find the server laptop IP:

```bash
ipconfig getifaddr en0
```

Then open this on another laptop/phone:

```text
http://<server-laptop-ip>:8000
```

If macOS asks, allow Docker or the terminal to accept incoming network connections.

## 7. Useful commands

```bash
docker compose logs -f
docker compose restart
docker compose down
docker compose up -d
```

Reset demo data:

```bash
docker compose exec factory-mvp python seed/seed_june_pdf_status.py
```

Backup SQLite database:

```bash
cp data/factory.db data/factory-backup-$(date +%Y%m%d-%H%M).db
```

## 8. What is persisted

- SQLite database: `data/factory.db`
- Generated PDF reports: `backend/generated_reports/`

Both are ignored by Git and remain on the server laptop.

## 9. Notes

- Do not commit `.env`, `data/`, generated reports, or local PDFs.
- The React frontend is built into the Docker image and served by FastAPI.
- `VITE_API_BASE_URL=/api/v1` means the frontend uses the same host as the backend.
- The AI assistant uses Gemini only when `GEMINI_API_KEY` is set.
