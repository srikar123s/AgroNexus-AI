# Production foundations

## Authentication and ownership

Set `AUTH_MODE=required` and a long random `JWT_SECRET` outside local
development. `POST /api/auth/register` and `/login` return bearer tokens.
Farmers can only list/use their own farms; `admin` and `advisor` accounts can
review farms. Password reset is two-step:
`/api/auth/password-reset/request` then `/confirm`. Reset secrets are never
emailed; the request endpoint only returns a token in demo mode so a local
operator can copy it to the confirmation request.

The frontend opens on a public welcome page and supports registration with an
email, username, password, and optional phone number. Existing users can log in
with any of those identifiers. Google sign-in is OAuth-ready through the
`VITE_GOOGLE_AUTH_URL` frontend setting, but production use still requires a
server-side Google callback and ID-token verification. A Google API key must
not be placed in the frontend or used as an OAuth client secret.

The in-process rate limiter is intentionally simple and safe for a single
instance. Use an API gateway or shared Redis limiter when horizontally scaling.
Set `ALLOWED_ORIGINS` to the exact frontend origins in hosted environments;
the local defaults allow only the Vite development addresses.

## Databases and backups

SQLite is the default. Set `DATABASE_URL` per environment (for example,
`postgresql+psycopg://user:password@host/agronexus`) and install the optional
`psycopg[binary]` dependency before introducing a PostgreSQL repository adapter.
Schema version `2` adds account, reset, weather-cache and soil-test tables.
SQLite backups can be made with:

```powershell
.\.venv\Scripts\python.exe -c "from database.maintenance import backup; backup('backend/database/agronexus.db','backups/agronexus.sqlite')"
```

Restore by calling `restore(backup, destination)` from
`backend.database.maintenance`. Keep backups outside source control.

## Agricultural data

`GET /api/weather?latitude=...&longitude=...` uses the configured provider with
timeouts, bounded retries and a SQLite cache. Responses expose `provider_status`,
`fetched_at`, `age_seconds`, `estimated`, and `stale`. A local estimate is always
returned when the provider is unavailable. `POST /api/soil-tests` records
structured farmer-entered lab values against an owned farm.
