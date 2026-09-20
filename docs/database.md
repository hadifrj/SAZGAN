# Database

Sazgan uses SQLite for local application persistence. Database access is centralized in `core/db.py` and schema changes are applied through the migration engine.

## Migrations

Check migration state:

```text
python scripts/migrate_db.py --status
python scripts/migrate_db.py --dry-run
python scripts/migrate_db.py
```

A normal migration creates a backup before applying pending changes.

## Adding a migration

Create the next numbered migration in `migrations/`, for example:

```text
migrations/0006_description.py
```

Implement an `upgrade(conn)` function and register the migration according to the existing migration engine conventions.

Never edit an already-applied migration. Create a new migration instead so existing installations remain reproducible and checksum verification stays meaningful.

## Data safety

The migration/update tooling is designed to preserve the live database. Release archives should never contain a production database, backups or uploaded customer files.

## Runtime locations

Typical runtime data includes:

- database files
- backups
- uploads
- logs
- local configuration

These are runtime concerns and are excluded from clean source releases.
