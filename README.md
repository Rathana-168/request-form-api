# Request Workflow API

FastAPI service for request forms with approval workflows. Each form is a plugin with its own table, validation, hooks and endpoints.

**Stack:** FastAPI · SQLAlchemy 2 (async) · PostgreSQL · Alembic · Redis · Celery · uv · Python 3.14

---

## Table of Contents
1. [Getting Started](#getting-started)
2. [Database Migrations](#database-migrations)
3. [Seed Data](#seed-data)
4. [Running the Services](#running-the-services)
5. [Project Structure](#project-structure)
6. [Form Plugins](#form-plugins)
7. [Troubleshooting](#troubleshooting)

---

## Getting Started

### 1. Requirements
- Python **3.14** (the code relies on 3.14's lazy type hints)
- [uv](https://docs.astral.sh/uv/)
- PostgreSQL 16 and Redis 7 (local, remote, or via `docker/docker-compose.yml`)

### 2. Install
```bash
git clone <repo-url>
cd request-workflow-api
uv python install 3.14
uv sync
```

### 3. Configure `.env`
Create `.env` in the project root:
```dotenv
SECRET_KEY=change-me
DEBUG=true

DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/workflow
DB_SCHEMA=workflow

REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/1
CELERY_RESULT_BACKEND=redis://localhost:6379/2
```

| Key | Note |
|---|---|
| `DATABASE_URL` | Must use the `postgresql+asyncpg://` driver |
| `DB_SCHEMA` | All tables go into this schema. Created automatically on the first migration |
| Host | Use `localhost` when the API runs outside Docker, `db` / `redis` when inside compose |

> `.env.local` and OS environment variables **override** `.env`. Check them first if the app connects to the wrong database.

### 4. Set up the database
```bash
uv run alembic upgrade head
uv run python -m scripts.seed
```

### 5. Run
```bash
uv run uvicorn app.main:app --reload
```
Swagger: http://localhost:8000/docs

---

## Database Migrations

### Apply migrations
Run after pulling new code or on a fresh database:
```bash
uv run alembic upgrade head
```

### Create a migration after changing models
1. Add or edit the model in `app/modules/<module>/models.py`
2. Make sure it is imported in `app/db/models.py`. Form plugin tables are picked up automatically by `load_plugins()`
3. Generate:
   ```bash
   uv run alembic revision --autogenerate -m "short description"
   ```
4. **Review** the new file in `migrations/versions/`. Remove anything unexpected, such as dropping `alembic_version` or tables you didn't touch
5. Apply:
   ```bash
   uv run alembic upgrade head
   ```

### Useful commands
| Command | Description |
|---|---|
| `uv run alembic current` | Current database version |
| `uv run alembic history` | List all migrations |
| `uv run alembic downgrade -1` | Roll back the last migration |

### How the schema works
- `app/db/session.py` and `migrations/env.py` set `search_path` to `DB_SCHEMA` on every connection
- Models have no `schema=`. Tables land in `DB_SCHEMA` automatically
- `alembic_version` also lives in `DB_SCHEMA`
- Do **not** add `version_table_schema` in `env.py`. It makes autogenerate try to drop `alembic_version`

---

## Seed Data

```bash
uv run python -m scripts.seed
```

Prompts:
| Prompt | Note |
|---|---|
| Superuser email | Used to log in |
| Full name | |
| Password | Min 8 characters, hidden while typing |

What it does:
- Inserts all permissions from `app/core/permissions.py`
- Creates an **Admin** role with every permission
- Creates the first superuser with the Admin role

Safe to run again. It only adds missing permissions and skips the superuser if one exists.

> Run it with `python -m scripts.seed` from the project root, not `python scripts/seed.py`, or the `app` imports won't resolve.

When you add a new permission to `app/core/permissions.py`, run the seed again to insert it.

---

## Running the Services

| Service | Command |
|---|---|
| Postgres + Redis (Docker) | `docker compose -f docker/docker-compose.yml up -d` |
| API | `uv run uvicorn app.main:app --reload` |
| Celery worker (macOS / Linux) | `uv run celery -A app.workers.celery_app worker -l info` |
| Celery worker (Windows) | `uv run celery -A app.workers.celery_app worker -l info --pool=solo` |

---

## Project Structure

```
app/
├── main.py                 # App factory, middleware, exception handlers
├── core/                   # config, security (JWT, Argon2), permissions, exceptions
├── db/                     # Base, session, mixins, types, models registry for Alembic
├── api/
│   ├── deps.py             # DbSession, CurrentUser, require_permission()
│   └── v1/router.py        # Mounts all module routers + form plugin routers
├── modules/                # Feature modules: router → service → repository → models
│   ├── auth/
│   ├── users/              # users, roles, permissions, departments
│   ├── forms/
│   │   ├── plugin.py       # FormDefinition, FormHooks, FormDataMixin
│   │   ├── registry.py     # Auto-discovers plugins → FORM_REGISTRY
│   │   └── definitions/    # One folder per form (see below)
│   └── requests/           # Request, RequestHistory, RequestCounter
├── workflow/               # Workflow models + engine
├── workers/                # Celery app and tasks
└── shared/                 # Page, PageParams, ORMModel
migrations/                 # Alembic
scripts/seed.py             # Permissions, Admin role, first superuser
docker/docker-compose.yml   # Postgres + Redis
```

### Request statuses
| Status | Editable by requester |
|---|---|
| `draft` | ✅ |
| `in_progress` | ❌ |
| `returned` | ✅ (edit and resubmit) |
| `approved` / `rejected` / `cancelled` | ❌ (final) |

Statuses are stored as `VARCHAR`, not a PostgreSQL enum, so adding a new value needs no migration.

---

## Form Plugins

Each form has its **own table** (typed columns, not JSON), its own validation and hooks, and optional custom endpoints. The `requests` and `workflow` modules only talk to forms through `FORM_REGISTRY`.

### Folder layout
```
app/modules/forms/definitions/
├── __init__.py              # required
└── leave_request/
    ├── __init__.py          # exports `definition`
    ├── constants.py
    ├── models.py            # the form's table
    ├── schemas.py           # create / update / read schemas
    ├── hooks.py             # business rules and lifecycle hooks
    └── router.py            # custom endpoints (optional)
```

### Add a new form
1. Copy `definitions/leave_request/` to `definitions/<your_form>/`
2. **`models.py`**: define the table. It must inherit `FormDataMixin, Base`, which gives it `id`, `request_id` (unique FK to `requests`) and timestamps. Prefix the table name with `form_`.
3. **`schemas.py`**:
   - `Create`: full payload with all required fields
   - `Update`: all fields optional, used when editing a draft or returned request
   - `Out`: response shape, also stored as the history snapshot
4. **`hooks.py`**: subclass `FormHooks` and override only what you need. Raise an `AppException` to block the action.

   | Hook | When it runs |
   |---|---|
   | `validate` | On submit, after schema validation (overlaps, balances...) |
   | `on_submit` | After `validate`, on submit and resubmit |
   | `on_approved` | All workflow steps approved |
   | `on_rejected` | Request rejected |
   | `on_returned` | Returned to requester for edits |
   | `on_cancelled` | Requester cancels |

5. **`router.py`** (optional): endpoints are mounted at `/api/v1/forms/<slug>/...`, where the slug is the code in lowercase with dashes (`LEAVE_REQUEST` → `leave-request`)
6. **`__init__.py`**: export the definition:
   ```python
   definition = FormDefinition(
       code="LEAVE_REQUEST",      # unique, matches forms.code
       prefix="LEAVE",            # unique, request no. → LEAVE-2026-00001
       model=LeaveRequestData,
       create_schema=LeaveCreate,
       update_schema=LeaveUpdate,
       read_schema=LeaveOut,
       hooks=LeaveHooks(),
       router=router,             # or omit
   )
   ```
7. Generate and apply a migration (see [Database Migrations](#database-migrations))
8. Register the form in the database:
   - `GET /api/v1/forms/available-codes` lists plugins without a DB row
   - `POST /api/v1/forms` with that code, name and category

The app refuses to start if two plugins share a `code` or a `prefix`, or if a plugin folder doesn't export `definition`.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `uv: command not found` | Install uv, then restart the terminal (or `source $HOME/.local/bin/env` on macOS) |
| `TypeError: 'function' object is not subscriptable` | You're on Python < 3.14. Run `uv python pin 3.14 && uv sync` |
| Tables created in `public` instead of `DB_SCHEMA` | `DB_SCHEMA` isn't being read. Check `.env`, `.env.local` and OS env vars |
| `relation "<schema>.alembic_version" does not exist` | Remove `version_table_schema` from `env.py` and delete the migration that drops `alembic_version` |
| Migration ran but pgAdmin shows no tables | pgAdmin is on another host/port/database, or needs a refresh on **Schemas → `<DB_SCHEMA>` → Tables** |
| `NoReferencedTableError ... 'workflows'` | A model has an FK to a table that doesn't exist yet. Add that model first, or remove the FK for now |
| Seed fails with `ModuleNotFoundError: app` | Run `python -m scripts.seed` from the project root |
| Windows: `uv sync` SSL error behind a proxy | `uv sync --system-certs` |