# Database Migration Guide

This project uses Alembic for database migrations (for SQLite auth database).

## Setup

Alembic is already configured in the project. The auth database uses SQLite and migrations help track schema changes.

## Creating Migrations

### Auto-generate migration from model changes

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "Add user role column"
```

### Create empty migration

```bash
alembic revision -m "Custom migration"
```

## Running Migrations

### Upgrade to latest

```bash
alembic upgrade head
```

### Upgrade by one version

```bash
alembic upgrade +1
```

### Downgrade by one version

```bash
alembic downgrade -1
```

### Show current version

```bash
alembic current
```

### Show migration history

```bash
alembic history --verbose
```

## Migration Files

Migrations are stored in `backend/alembic/versions/`.

Example migration:

```python
"""Add user warehouse_id

Revision ID: abc123
Revises: def456
Create Date: 2024-01-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'abc123'
down_revision = 'def456'
branch_labels = None
depends_on = None

def upgrade():
    """Upgrade database."""
    op.add_column('users', sa.Column('warehouse_id', sa.Integer(), nullable=True))

def downgrade():
    """Rollback changes."""
    op.drop_column('users', 'warehouse_id')
```

## Best Practices

### Before Creating Migrations

1. **Test locally** - Always test migrations on local database first
2. **Review SQL** - Check generated SQL with `alembic upgrade head --sql`
3. **Backup data** - Always backup database before migrations

### Migration Guidelines

1. **One change per migration** - Easier to rollback
2. **Test rollback** - Ensure `downgrade()` works
3. **Add data migrations carefully** - Consider large datasets
4. **Use transactions** - Most migrations should be transactional

### Production Deployment

```bash
# 1. Backup database
cp auth.db auth.db.backup

# 2. Test migration with SQL output
alembic upgrade head --sql > migration.sql
cat migration.sql  # Review changes

# 3. Run migration
alembic upgrade head

# 4. Verify
alembic current
```

## Configuration

Alembic configuration in `backend/alembic.ini`:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = sqlite:///./auth.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic
```

## Troubleshooting

### "Can't locate revision abc123"

Reset migration history:
```bash
alembic stamp head
```

### "Target database is not up to date"

Check current version:
```bash
alembic current
alembic history
```

### Rollback failed migration

```bash
# Manual rollback
alembic downgrade -1

# Or restore from backup
cp auth.db.backup auth.db
```

## Future: Odoo Data Migrations

Odoo ERP has its own migration system. This Alembic setup is only for the local SQLite auth database.

For Odoo data:
- Use Odoo's built-in migration framework
- Or create custom migration scripts using Odoo XML-RPC API

## Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [Database Migration Best Practices](https://www.prisma.io/dataguide/types/relational/migration-strategies)
