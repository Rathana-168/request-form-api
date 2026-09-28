## Database Migrations (Alembic)

### 1. Check your database connection

Make sure `DATABASE_URL` in `.env` points to the correct PostgreSQL database.

### 2. Apply existing migrations

Run this after pulling new code or setting up a fresh database:

```bash
uv run alembic upgrade head
```

### 3. Create a new migration (after changing models)

1. Add or edit your model in `app/modules/<module>/models.py`
2. Make sure the model is imported in `app/db/base.py`
3. Generate the migration:

```bash
   uv run alembic revision --autogenerate -m "short description"
```

4. Review the new file in `migrations/versions/`
5. Apply it:

```bash
   uv run alembic upgrade head
```

### Useful commands

| Command                       | Description                   |
| ----------------------------- | ----------------------------- |
| `uv run alembic current`      | Show current database version |
| `uv run alembic history`      | List all migrations           |
| `uv run alembic downgrade -1` | Roll back the last migration  |

### Using Docker

```bash
docker compose exec api alembic upgrade head
```
