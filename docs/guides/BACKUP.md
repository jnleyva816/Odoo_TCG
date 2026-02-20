# Backup and Restore Guide

Comprehensive guide for backing up and restoring the TCG Inventory System.

## What to Backup

### 1. Odoo Database (Primary - CRITICAL)
- **Location**: Odoo server (PostgreSQL)
- **Contains**:
  - User accounts and authentication
  - Product catalog (TCG cards)
  - Inventory data
  - All business data
- **Critical**: Yes - main data store
- **Note**: Use Odoo's backup tools (see below)

### 2. Optional Local Database (SQLite)
- **Location**: `backend/auth.db` (if exists)
- **Contains**: Login attempt tracking, session data (auxiliary features only)
- **Critical**: No - Odoo handles authentication
- **Note**: This is optional and only used for security monitoring

### 3. Environment Configuration
- **Location**: `.env` files
- **Contains**: Secrets, API keys, configuration
- **Critical**: Yes - required to start system

### 4. Docker Volumes (if using Docker)
- **redis-data**: Cache data (not critical, regenerates)
- **meili-data**: Search index (not critical, can reindex)

## Backup Scripts

### Manual Backup Script

```bash
#!/bin/bash
# backup.sh - Manual backup script

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "🔄 Creating backup..."

# 1. Backup optional auth database (if exists)
if [ -f "backend/auth.db" ]; then
    cp backend/auth.db "$BACKUP_DIR/auth.db"
    echo "✅ Local auth database backed up (optional - used for login tracking)"
else
    echo "ℹ️  No local auth.db found (authentication via Odoo)"
fi

# 2. Backup environment config (without secrets)
if [ -f ".env" ]; then
    # Copy but remove sensitive values
    grep -v "PASSWORD\|SECRET\|KEY" .env > "$BACKUP_DIR/env.template"
    echo "✅ Config template backed up"
fi

# 3. Backup Docker volumes (if using Docker)
if command -v docker &> /dev/null; then
    docker run --rm \
        -v tcg-redis-data:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine tar czf /backup/redis-data.tar.gz /data

    docker run --rm \
        -v tcg-meili-data:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine tar czf /backup/meili-data.tar.gz /data

    echo "✅ Docker volumes backed up"
fi

# 4. Create backup manifest
cat > "$BACKUP_DIR/MANIFEST.txt" << EOF
Backup created: $(date)
System version: 2.0.0
Auth DB: $([ -f "$BACKUP_DIR/auth.db" ] && echo "Yes" || echo "No")
Config: $([ -f "$BACKUP_DIR/env.template" ] && echo "Yes" || echo "No")
Redis: $([ -f "$BACKUP_DIR/redis-data.tar.gz" ] && echo "Yes" || echo "No")
Meilisearch: $([ -f "$BACKUP_DIR/meili-data.tar.gz" ] && echo "Yes" || echo "No")
EOF

echo "✅ Backup complete: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"
```

### Automated Daily Backup

```bash
#!/bin/bash
# daily-backup.sh - Automated backup with retention

BACKUP_ROOT="backups"
RETENTION_DAYS=30

# Create backup
./backup.sh

# Clean old backups (keep last 30 days)
find "$BACKUP_ROOT" -type d -mtime +$RETENTION_DAYS -exec rm -rf {} +

echo "✅ Old backups cleaned (keeping last $RETENTION_DAYS days)"
```

Setup cron job:
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/daily-backup.sh >> /var/log/tcg-backup.log 2>&1
```

## Restore Procedures

### Restore Auth Database

```bash
#!/bin/bash
# restore-auth.sh - Restore auth database

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Stop application
docker compose down

# Backup current DB (just in case)
cp backend/auth.db backend/auth.db.pre-restore

# Restore from backup
cp "$BACKUP_FILE" backend/auth.db

# Restart application
docker compose up -d

echo "✅ Auth database restored from $BACKUP_FILE"
```

### Full System Restore

```bash
#!/bin/bash
# restore-full.sh - Full system restore

BACKUP_DIR="$1"

if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
    echo "Usage: $0 <backup_directory>"
    exit 1
fi

echo "🔄 Restoring from $BACKUP_DIR..."

# Stop services
docker compose down

# Restore auth database
if [ -f "$BACKUP_DIR/auth.db" ]; then
    cp "$BACKUP_DIR/auth.db" backend/auth.db
    echo "✅ Auth database restored"
fi

# Restore Docker volumes
if [ -f "$BACKUP_DIR/redis-data.tar.gz" ]; then
    docker run --rm \
        -v tcg-redis-data:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine sh -c "cd / && tar xzf /backup/redis-data.tar.gz"
    echo "✅ Redis data restored"
fi

if [ -f "$BACKUP_DIR/meili-data.tar.gz" ]; then
    docker run --rm \
        -v tcg-meili-data:/data \
        -v "$(pwd)/$BACKUP_DIR":/backup \
        alpine sh -c "cd / && tar xzf /backup/meili-data.tar.gz"
    echo "✅ Meilisearch data restored"
fi

# Note about env file
if [ -f "$BACKUP_DIR/env.template" ]; then
    echo "⚠️  Remember to restore secrets in .env file!"
    echo "   Template available at: $BACKUP_DIR/env.template"
fi

# Restart services
docker compose up -d

echo "✅ Restore complete!"
```

## Odoo Backup

### Backup Odoo Database

Using Odoo Web Interface:
1. Go to Settings → Database Manager
2. Click "Backup"
3. Choose ZIP format (includes filestore)
4. Download backup file

Using Odoo CLI:
```bash
# Backup single database
odoo-bin -d tcg-cards --db_host=localhost --db_port=5432 \
    --db_user=odoo --db_password=odoo \
    -r backup --backup-dir=/path/to/backups

# Or use pg_dump directly
pg_dump -h localhost -U odoo tcg-cards > tcg-cards-backup.sql
```

### Restore Odoo Database

Using Odoo Web Interface:
1. Go to Settings → Database Manager
2. Click "Restore"
3. Upload backup file
4. Enter new database name
5. Click "Restore"

Using psql:
```bash
# Create new database
createdb -h localhost -U odoo tcg-cards-restored

# Restore from backup
psql -h localhost -U odoo tcg-cards-restored < tcg-cards-backup.sql
```

## Backup Best Practices

### Frequency

- **Auth Database**: Daily
- **Odoo Database**: Daily + before major changes
- **Configuration**: After each change
- **Docker Volumes**: Weekly (cache/search data, not critical)

### Storage

1. **Local Backups**: Keep last 30 days
2. **Off-site Backups**: Weekly to cloud storage
3. **Archive**: Monthly backups kept for 1 year

### Automation

```bash
# Use systemd timer or cron
# /etc/systemd/system/tcg-backup.timer
[Unit]
Description=TCG Backup Timer

[Timer]
OnCalendar=daily
OnCalendar=02:00

[Install]
WantedBy=timers.target
```

### Verification

```bash
# Test restore monthly
mkdir -p test-restore
./restore-full.sh backups/latest test-restore
# Verify data integrity
# Clean up test restore
```

## Cloud Backup (Optional)

### AWS S3

```bash
#!/bin/bash
# backup-to-s3.sh

BACKUP_DIR="backups/$(date +%Y%m%d)"
S3_BUCKET="s3://my-tcg-backups"

# Create local backup
./backup.sh

# Upload to S3
aws s3 sync "$BACKUP_DIR" "$S3_BUCKET/$BACKUP_DIR" \
    --storage-class STANDARD_IA

# Clean old S3 backups (keep 90 days)
aws s3 ls "$S3_BUCKET/" | while read -r line; do
    createDate=$(echo "$line" | awk '{print $1" "$2}')
    createDate=$(date -d "$createDate" +%s)
    olderThan=$(date -d "90 days ago" +%s)
    if [[ $createDate -lt $olderThan ]]; then
        folder=$(echo "$line" | awk '{print $4}')
        aws s3 rm --recursive "$S3_BUCKET/$folder"
    fi
done
```

### Encrypted Backups

```bash
#!/bin/bash
# encrypted-backup.sh

BACKUP_FILE="backup-$(date +%Y%m%d).tar.gz"
ENCRYPTED_FILE="$BACKUP_FILE.gpg"

# Create archive
tar czf "$BACKUP_FILE" backend/auth.db .env

# Encrypt with GPG
gpg --symmetric --cipher-algo AES256 "$BACKUP_FILE"

# Remove unencrypted archive
rm "$BACKUP_FILE"

echo "✅ Encrypted backup: $ENCRYPTED_FILE"
```

Decrypt:
```bash
gpg --decrypt backup-20240111.tar.gz.gpg > backup-20240111.tar.gz
```

## Disaster Recovery

### Recovery Time Objective (RTO)

- **Target**: < 1 hour
- **Steps**: Restore from last backup, restart services
- **Dependencies**: Backup availability, Odoo restore time

### Recovery Point Objective (RPO)

- **Target**: < 24 hours (daily backups)
- **Improve**: Increase backup frequency for critical periods

### Emergency Contacts

Document in your runbook:
- Odoo administrator
- Database administrator
- System administrator
- On-call engineer

## Monitoring

### Backup Health Checks

```bash
#!/bin/bash
# check-backups.sh

LATEST_BACKUP=$(ls -t backups/ | head -1)
BACKUP_AGE=$(stat -c %Y "backups/$LATEST_BACKUP")
NOW=$(date +%s)
AGE_HOURS=$(( ($NOW - $BACKUP_AGE) / 3600 ))

if [ $AGE_HOURS -gt 48 ]; then
    echo "⚠️ WARNING: Last backup is $AGE_HOURS hours old!"
    # Send alert
else
    echo "✅ Backups are current (last: $AGE_HOURS hours ago)"
fi
```

## Checklist

### Daily
- [ ] Verify backup job ran
- [ ] Check backup file sizes
- [ ] Monitor backup storage space

### Weekly
- [ ] Review backup logs
- [ ] Test a restore procedure
- [ ] Verify off-site backups

### Monthly
- [ ] Full restore test
- [ ] Review retention policy
- [ ] Update documentation

### Quarterly
- [ ] Disaster recovery drill
- [ ] Review and update procedures
- [ ] Audit backup security

## Resources

- [PostgreSQL Backup](https://www.postgresql.org/docs/current/backup.html)
- [Docker Volume Backups](https://docs.docker.com/storage/volumes/#backup-restore-or-migrate-data-volumes)
- [3-2-1 Backup Rule](https://www.backblaze.com/blog/the-3-2-1-backup-strategy/)
