# Factory Owner MVP

FastAPI + React MVP for a PO-driven, stage-based textile factory execution system.

For moving the project to a second laptop and running it as a local test server, start with:

[SERVER_LAPTOP_SETUP.md](SERVER_LAPTOP_SETUP.md)

## Includes

- Async SQLAlchemy 2.0 models for products, purchase orders, fabric plans, stages, contractors, progress, dispatch loads, alerts, and users.
- Pydantic v2 schemas with strict quantity and date validation.
- Service-owned business rules for fabric shortage detection, partial stage movement, contractor progress, quality failure actions, packing analysis, dispatch costing, alert generation, and owner dashboard aggregation.
- JWT authentication.

## Run Backend Locally

```bash
cd backend
uvicorn app.main:app --reload
```

## Run Full App With Docker

```bash
docker compose up --build
```

The app is available at `http://127.0.0.1:8000`.

Seed the current June owner-demo data:

```bash
docker compose exec factory-mvp python seed/seed_june_pdf_status.py
```
