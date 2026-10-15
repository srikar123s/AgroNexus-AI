# AgroNexus database

`schema.sql` defines the persistence layer for the adaptive decision loop. It uses SQLite and only Python's standard library, so it can be initialized before the API framework is selected.

Run from the project root:

```powershell
& 'C:\Users\srikar\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' backend\database\database.py
```

The command creates `backend/database/agronexus.db`, which is ignored by Git and can be recreated from the schema. Schema version 2 includes users, password-reset tokens, weather cache and soil tests. `DATABASE_URL` is environment-configurable; SQLite is the default and PostgreSQL deployments should install `psycopg[binary]` and use the same versioned schema through the deployment migration process.

For a point-in-time SQLite backup/restore use `database.maintenance.backup` and
`database.maintenance.restore` (never commit backup files).

## Core flow

```text
farm and field
  -> decision and evidence items
  -> ERP sufficiency result and deficits
  -> candidate actions and recommendation
  -> outcome feedback
  -> ACER record and context features
  -> CNDA attributions
  -> action-context relationship and ERP update logs
```

Every recommendation retains its ERP version, evidence values, candidate scores, decision trace, and context snapshot. Every adaptive update retains its source ACER and the before/after values. This makes experimental results reproducible and recommendations auditable.
