# Database Migration Guide

## Overview

This project uses **Odoo ERP as the primary authentication and data storage system**. User authentication is handled directly through Odoo's `res.users` model via XML-RPC, eliminating the need for a separate authentication database.

## Current Architecture

- **Primary Data Store**: Odoo ERP (PostgreSQL)
  - User accounts and authentication
  - Product catalog (TCG cards)
  - Inventory management
  - All business data

- **Optional Local Storage**: SQLite (if used)
  - Login attempt tracking (security monitoring)
  - Session management
  - These are auxiliary features, not core authentication

## No Traditional Migrations Needed

Since authentication and core data are managed by Odoo, this application **does not require database migrations** in the traditional sense. Schema changes are managed by Odoo's own migration system.

## Odoo Schema Changes

If you need to modify the Odoo data schema (add fields to products, users, etc.):

### 1. Odoo Module Development

The proper way to modify Odoo schema is through Odoo modules:

```python
# In your custom Odoo module
from odoo import models, fields

class ResUsers(models.Model):
    _inherit = 'res.users'
    
    # Add custom field
    preferred_warehouse_id = fields.Many2one(
        'stock.warehouse',
        string='Preferred Warehouse'
    )
```

### 2. Odoo Database Upgrades

```bash
# Upgrade specific module
odoo-bin -u module_name -d database_name

# Or via Odoo UI
# Apps → Update Apps List → Upgrade Module
```

### 3. XML-RPC Schema Access

For read-only schema inspection:

```python
import xmlrpc.client

# Connect to Odoo
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Get field definitions
fields = models.execute_kw(
    db, uid, password,
    'res.users', 'fields_get',
    [], {'attributes': ['string', 'type', 'required']}
)
```

## Data Migration Scripts

For bulk data changes or imports, use Python scripts with the Odoo API:

```python
# scripts/migrate_data.py
import xmlrpc.client
from dotenv import load_dotenv
import os

load_dotenv()

# Connect
url = os.getenv('ODOO_URL')
db = os.getenv('ODOO_DB')
username = os.getenv('ODOO_USER')
password = os.getenv('ODOO_PASSWORD')

common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})

models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')

# Example: Update all products
product_ids = models.execute_kw(
    db, uid, password,
    'product.product', 'search',
    [[]]  # Search all
)

for product_id in product_ids:
    models.execute_kw(
        db, uid, password,
        'product.product', 'write',
        [[product_id], {'some_field': 'new_value'}]
    )

print(f"Updated {len(product_ids)} products")
```

## Best Practices

### Schema Changes

1. **Always backup Odoo database** before schema changes
2. **Test in staging environment** first
3. **Use Odoo modules** for permanent schema changes
4. **Document custom fields** in module documentation
5. **Version control Odoo modules** in separate repository

### Data Migrations

1. **Create scripts in `scripts/migrations/`** directory
2. **Test with small dataset** first
3. **Use transactions** when possible
4. **Log all changes** for audit trail
5. **Keep rollback scripts** ready

### Production Deployment

```bash
# 1. Backup Odoo database
pg_dump -h localhost -U odoo database_name > backup.sql

# 2. Test changes in staging
# Apply Odoo module upgrade or run migration script

# 3. Verify data integrity
# Run validation queries

# 4. Apply to production
# Deploy Odoo module or run migration script

# 5. Monitor for issues
# Check Odoo logs: /var/log/odoo/odoo.log
```

## Local SQLite (Optional)

If you're using local SQLite for auxiliary features (login attempts, sessions), you can set up Alembic:

```bash
# Install Alembic (not included by default)
pip install alembic

# Initialize Alembic
cd backend
alembic init alembic

# Configure alembic.ini
# sqlalchemy.url = sqlite:///./auth.db

# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

**Note**: This is optional and only needed if you're adding custom SQLite tables for application-specific features.

## Troubleshooting

### Odoo Connection Issues

```bash
# Test Odoo connectivity
python3 << EOF
import xmlrpc.client
common = xmlrpc.client.ServerProxy('http://odoo-server:8069/xmlrpc/2/common')
print(common.version())
EOF
```

### Data Inconsistencies

```bash
# Check Odoo data directly
psql -h localhost -U odoo -d database_name -c "SELECT * FROM res_users LIMIT 5;"
```

### Migration Failures

- **Always have database backup** before attempting changes
- Use Odoo's built-in backup/restore functionality
- Test migrations in isolated environment first

## Resources

- [Odoo Development Documentation](https://www.odoo.com/documentation/16.0/developer.html)
- [Odoo ORM API](https://www.odoo.com/documentation/16.0/developer/reference/backend/orm.html)
- [Odoo External API (XML-RPC)](https://www.odoo.com/documentation/16.0/developer/reference/external_api.html)
- [PostgreSQL Backup](https://www.postgresql.org/docs/current/backup.html)
- [Alembic Documentation](https://alembic.sqlalchemy.org/) (for optional SQLite migrations)
