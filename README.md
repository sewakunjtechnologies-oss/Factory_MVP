# Factory Owner MVP Backend

FastAPI backend for a PO-driven, stage-based textile factory execution system.

## Includes

- Async SQLAlchemy 2.0 models for products, purchase orders, fabric plans, stages, contractors, progress, dispatch loads, alerts, and users.
- Pydantic v2 schemas with strict quantity and date validation.
- Service-owned business rules for fabric shortage detection, partial stage movement, contractor progress, quality failure actions, packing analysis, dispatch costing, alert generation, and owner dashboard aggregation.
- JWT authentication.

## Run

```bash
cd backend
uvicorn app.main:app --reload
```

## Run With Docker

```bash
cd backend
docker compose up --build
```

The Compose stack starts:

- API: `http://127.0.0.1:8000`
- PostgreSQL container: internal `postgres:5432`, host `127.0.0.1:5433`
- Redis container: internal `redis:6379`, host `127.0.0.1:6380`

The API container uses:

```text
DATABASE_URL=postgresql+psycopg://postgres:postgres@postgres:5432/factory_mvp
REDIS_URL=redis://redis:6379/0
```

Postgres loads `backend/schema.sql` on first volume creation. If you change the schema after the first run, remove the volume and restart:

```bash
docker compose down -v
docker compose up --build
```
