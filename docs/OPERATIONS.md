# Agentic SQL Analyst - Operations Guide

## Supported runtime

- Python 3.11
- PostgreSQL
- Gemini API access

Use `setup_windows.cmd` on Windows. It calls `venv\Scripts\python.exe`
directly, validates Python 3.11, and works without activation. Do not run the
PowerShell-only `Activate.ps1` from Command Prompt, and do not install this
dependency set with system Python 3.14.

## First-time setup

```bat
cd /d D:\agentic-sql
setup_windows.cmd
```

In PowerShell, invoke the same launcher as `.\setup_windows.cmd`. It creates the
Python 3.11 venv if necessary, installs and validates dependencies, creates
`.env` only when absent, and never overwrites an existing `.env`.

Copy `.env.example` to `.env`. At minimum, configure PostgreSQL, `GEMINI_API_KEY`, and a unique long `JWT_SECRET_KEY`.

Generate a JWT secret:

```bat
venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Database schema

The backend launcher runs a safe migration bootstrap automatically. Run it manually with:

```bat
venv\Scripts\python.exe -m database.migrate
```

It detects new databases, the previous unversioned `create_all()` schema, already-upgraded unversioned databases, and unsafe partial schemas. Partial schemas stop for manual review.

Standard commands:

```bat
venv\Scripts\python.exe -m alembic current
venv\Scripts\python.exe -m alembic heads
venv\Scripts\python.exe -m alembic upgrade head
```

Back up production databases before migration.

## Demo data and RAG

```bat
venv\Scripts\python.exe -m practice.load_data
venv\Scripts\python.exe -m rag.build_index
```

## Start the platform

Terminal 1:

```bat
cd /d D:\agentic-sql
run_backend.cmd
```

Terminal 2:

```bat
cd /d D:\agentic-sql
run_frontend.cmd
```

- UI: `http://localhost:8501`
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

## Password reset

Development uses console delivery by default. The backend console prints the reset link while the API always returns the same generic response for known and unknown accounts.

```env
APP_ENV=development
EMAIL_DELIVERY_MODE=console
PASSWORD_RESET_BASE_URL=http://localhost:8501
```

Production must use SMTP:

```env
APP_ENV=production
EMAIL_DELIVERY_MODE=smtp
PASSWORD_RESET_BASE_URL=https://analytics.example.com
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_username
SMTP_PASSWORD=your_password
SMTP_FROM_EMAIL=analytics@example.com
SMTP_USE_SSL=false
SMTP_USE_STARTTLS=true
```

Production rejects weak/default JWT secrets and refuses console or disabled reset delivery.

## Tests

```bat
venv\Scripts\python.exe -m pytest -q
```

The deterministic suite covers authentication and recovery, JWT revocation, rate limits, ownership isolation, CSV/XLSX imports, profiling, migration paths, API contracts, report privacy, SQL parser bypasses, table-scoped correction, CTE handling, unsafe functions, and outer result limits.

Live PostgreSQL and Gemini verification uses the services configured in `.env`.

## Production checklist

- Set `APP_ENV=production`.
- Use HTTPS and a secret manager.
- Restrict `CORS_ORIGINS` and `TRUSTED_HOSTS`.
- Configure SMTP and a unique reset-token pepper.
- Run migrations before starting new workers.
- Use a least-privilege PostgreSQL role.
- Replace the in-process rate limiter with Redis for multi-worker deployments.
- Centralize request-ID logs and monitor authentication, model, and database failures.
- Define uploaded-data and report retention/backup policies.
