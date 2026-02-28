# Overwatch Cloud

Backend API for the Overwatch autonomous perching drone mesh system. Serves as the system of record for venue intelligence, kit/drone registry, world model knowledge, and workstation synchronisation.

Built with FastAPI, SQLAlchemy, PostgreSQL + pgvector, and S3-compatible blob storage.

## Quick Start

```bash
cp .env.example .env
docker-compose up
```

This starts PostgreSQL 16 (with pgvector), MinIO (S3-compatible blob storage), and the API server on `http://localhost:8000`.

API docs are available at `http://localhost:8000/docs`.

## Local Development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env to point DATABASE_URL at your local PostgreSQL

# Run migrations
alembic upgrade head

# Start the server
uvicorn main:app --reload --port 8000
```

## Project Structure

```
overwatch-cloud/
├── main.py                  # FastAPI app entry point
├── app/
│   ├── core/config.py       # Pydantic settings (.env)
│   ├── database/            # Engine, session, declarative base
│   ├── models/              # 17 SQLAlchemy models
│   ├── api/                 # Route modules
│   │   ├── auth.py          # Customer provisioning, workstation registration
│   │   ├── kits.py          # Kit registry + drone assignments
│   │   ├── sync.py          # Delta push/pull, bootstrap
│   │   ├── venues.py        # Venue CRUD + search
│   │   ├── operations.py    # Operation records
│   │   ├── world_model.py   # Knowledge graph nodes/edges
│   │   └── blobs.py         # Presigned upload/download URLs
│   ├── services/
│   │   ├── sync_service.py  # Delta resolution, conflict handling
│   │   ├── venue_merge.py   # Multi-workstation venue merging
│   │   └── blob_service.py  # S3-compatible presigned URLs
│   └── observability.py     # Prometheus metrics, structured logging
├── migrations/              # Alembic
├── docker-compose.yml       # PostgreSQL + pgvector, MinIO, app
├── Dockerfile
└── requirements.txt
```

## API Overview

All routes are prefixed with `/api/v1`. Authentication is via `X-API-Key` header (per-customer).

| Endpoint Group         | Description                                      |
|------------------------|--------------------------------------------------|
| `POST /auth/customers` | Provision a customer, returns one-time API key   |
| `POST /auth/workstations/register` | Register a workstation             |
| `GET /kits`            | List kits for the authenticated customer         |
| `GET /kits/{serial}`   | Fetch kit by serial (used during onboarding)     |
| `POST /sync/push`      | Push changed entities from a workstation         |
| `GET /sync/pull`       | Pull entities changed since a given version      |
| `GET /sync/bootstrap`  | Full state download for new workstation setup    |
| `GET/POST /venues`     | Venue CRUD and search                            |
| `GET/POST /operations` | Operation records                                |
| `GET/POST /world-model/nodes` | World model knowledge graph nodes         |
| `GET/POST /world-model/edges` | World model knowledge graph edges         |
| `GET /blobs/upload-url`   | Presigned PUT URL for blob upload             |
| `GET /blobs/download-url` | Presigned GET URL for blob download           |
| `GET /health`          | Health check                                     |
| `GET /metrics`         | Prometheus metrics                               |

## Database Migrations

```bash
# Generate a new migration after model changes
alembic revision --autogenerate -m "describe the change"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `API_KEY_PEPPER` | Yes | Secret pepper for API key hashing |
| `CORS_ORIGINS` | No | JSON array of allowed origins |
| `BLOB_STORAGE_ENDPOINT` | No | S3-compatible endpoint (MinIO for dev) |
| `BLOB_STORAGE_ACCESS_KEY` | No | S3 access key |
| `BLOB_STORAGE_SECRET_KEY` | No | S3 secret key |
| `BLOB_STORAGE_BUCKET` | No | Bucket name (default: `overwatch-blobs`) |
| `BLOB_PRESIGN_EXPIRY_SECONDS` | No | Presigned URL expiry (default: 900) |

## Part of the Overwatch System

This is one of four independently deployed components:

- **overwatch-cloud** (this repo) — Backend API and system of record
- **overwatch-control** — Command workstation Electron app
- **overwatch-companion** — Field agent mobile app
- **overwatch-dashboard** — Customer-facing web dashboard
