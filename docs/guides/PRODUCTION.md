# Production Deployment Best Practices

Comprehensive guide for deploying the TCG Inventory System to production.

## Pre-Deployment Checklist

### Security
- [ ] Generate strong JWT secret: `openssl rand -hex 32` <!-- pragma: allowlist secret -->
- [ ] Use strong database passwords
- [ ] Enable HTTPS (use reverse proxy)
- [ ] Configure firewall rules
- [ ] Review security headers in middleware
- [ ] Set `DEBUG=false` in production
- [ ] Configure CORS for production domains only
- [ ] Enable rate limiting (already configured)
- [ ] Set up fail2ban or similar
- [ ] Review `.gitignore` - no secrets committed

### Configuration
- [ ] Create production `.env` file
- [ ] Set production Odoo credentials
- [ ] Configure email notifications
- [ ] Set up Meilisearch master key
- [ ] Configure Redis persistence
- [ ] Set log level to INFO or WARNING
- [ ] Enable JSON logging format
- [ ] Configure backup schedule

### Infrastructure
- [ ] Minimum 2GB RAM, 2 CPU cores
- [ ] SSD storage for database
- [ ] Regular backup storage
- [ ] Monitoring tools installed
- [ ] Log aggregation configured
- [ ] SSL certificates obtained
- [ ] DNS configured
- [ ] Reverse proxy setup (nginx/Traefik)

### Dependencies
- [ ] Docker 24+ installed
- [ ] Docker Compose V2 installed
- [ ] Odoo 16+ instance running
- [ ] Network connectivity to Odoo
- [ ] Sufficient disk space (10GB+ recommended)

## Deployment Methods

### Method 1: Docker Compose (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/jnleyva816/Odoo_TCG.git
cd Odoo_TCG

# 2. Configure environment
cp env.example .env
nano .env  # Edit with production values

# 3. Build and start services
cd docker
docker compose up -d --build

# 4. Check logs
docker compose logs -f

# 5. Verify health
curl http://localhost:8000/api/health
```

### Method 2: Systemd Services

```bash
# 1. Create systemd service files
sudo nano /etc/systemd/system/tcg-backend.service
```

```ini
[Unit]
Description=TCG Inventory Backend
After=network.target

[Service]
Type=simple
User=tcg
WorkingDirectory=/opt/tcg-inventory
Environment="PATH=/opt/tcg-inventory/venv/bin"
ExecStart=/opt/tcg-inventory/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
# 2. Enable and start
sudo systemctl enable tcg-backend
sudo systemctl start tcg-backend

# 3. Check status
sudo systemctl status tcg-backend
```

### Method 3: Manual Deployment

```bash
# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (build static files)
cd frontend
npm install
npm run build
# Serve dist/ with nginx or similar
```

## Reverse Proxy Setup

### Nginx Configuration

```nginx
# /etc/nginx/sites-available/tcg-inventory
server {
    listen 80;
    server_name tcg.yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name tcg.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/tcg.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tcg.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    # Frontend (static files)
    location / {
        root /opt/tcg-inventory/frontend/dist;
        try_files $uri $uri/ /index.html;

        # Cache static assets
        location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;

        # Buffer settings
        proxy_buffering off;
        proxy_request_buffering off;
    }

    # API docs
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # Health check (for monitoring)
    location /health {
        proxy_pass http://localhost:8000/api/health;
        access_log off;
    }
}
```

Enable configuration:
```bash
sudo ln -s /etc/nginx/sites-available/tcg-inventory /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Traefik Configuration (Docker)

```yaml
# docker/docker-compose.traefik.yml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@yourdomain.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - traefik-certs:/letsencrypt

  backend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`tcg.yourdomain.com`) && PathPrefix(`/api`)"
      - "traefik.http.routers.backend.entrypoints=websecure"
      - "traefik.http.routers.backend.tls.certresolver=letsencrypt"
      - "traefik.http.services.backend.loadbalancer.server.port=8000"

  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`tcg.yourdomain.com`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
      - "traefik.http.services.frontend.loadbalancer.server.port=80"

volumes:
  traefik-certs:
```

## SSL/TLS Setup

### Let's Encrypt with Certbot

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d tcg.yourdomain.com

# Test auto-renewal
sudo certbot renew --dry-run
```

## Monitoring

### Health Checks

```bash
# Kubernetes liveness probe
livenessProbe:
  httpGet:
    path: /api/health
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 30

# Kubernetes readiness probe
readinessProbe:
  httpGet:
    path: /api/health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 10
```

### Uptime Monitoring

Set up external monitoring:
- UptimeRobot
- Pingdom
- StatusCake
- Custom script with cron

```bash
# monitor.sh
#!/bin/bash
URL="https://tcg.yourdomain.com/api/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $URL)

if [ $RESPONSE -ne 200 ]; then
    echo "Service down! HTTP $RESPONSE"
    # Send alert email/SMS
fi
```

### Log Monitoring

```bash
# View logs
docker compose logs -f backend

# Search logs
docker compose logs backend | grep ERROR

# Export logs to file
docker compose logs --since 24h backend > logs.txt
```

## Backup Strategy

### Automated Backups

```bash
# Add to crontab
crontab -e

# Daily backup at 2 AM
0 2 * * * /opt/tcg-inventory/scripts/backup/backup.sh >> /var/log/tcg-backup.log 2>&1

# Weekly cleanup (keep 30 days)
0 3 * * 0 find /opt/tcg-inventory/backups -type d -mtime +30 -exec rm -rf {} +
```

## Scaling

### Horizontal Scaling

```yaml
# docker-compose.scale.yml
services:
  backend:
    deploy:
      replicas: 3

  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
```

Load balancer config:
```nginx
upstream backend {
    least_conn;
    server backend-1:8000;
    server backend-2:8000;
    server backend-3:8000;
}
```

### Vertical Scaling

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
```

## Security Hardening

### Firewall Rules (UFW)

```bash
# Allow SSH
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Deny everything else
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Enable firewall
sudo ufw enable
```

### Docker Security

```bash
# Run containers as non-root
USER node  # In Dockerfile

# Drop capabilities
security_opt:
  - no-new-privileges:true
cap_drop:
  - ALL
cap_add:
  - NET_BIND_SERVICE

# Use read-only filesystem
read_only: true
tmpfs:
  - /tmp
```

## Updates and Maintenance

### Update Procedure

```bash
# 1. Backup current state
./scripts/backup/backup.sh

# 2. Pull latest code
git fetch origin
git checkout v2.1.0  # or latest tag

# 3. Update dependencies
cd backend && pip install -U -e . && cd ..
cd frontend && npm install && npm run build && cd ..

# 4. Rebuild containers
cd docker
docker compose pull
docker compose up -d --build

# 5. Run migrations (if any)
docker compose exec backend alembic upgrade head

# 6. Verify
curl https://tcg.yourdomain.com/api/health

# 7. Monitor logs
docker compose logs -f --tail=100
```

### Zero-Downtime Deployment

```bash
# Using Docker with health checks
docker compose up -d --no-deps --build backend
docker compose up -d --no-deps --build frontend
```

## Troubleshooting

### Common Issues

**Backend won't start:**
```bash
# Check logs
docker compose logs backend

# Check Odoo connection
docker compose exec backend python -c "from app.services.odoo import OdooService; from app.config import get_settings; import asyncio; asyncio.run(OdooService(get_settings()).connect())"
```

**High memory usage:**
```bash
# Monitor resources
docker stats

# Restart services
docker compose restart
```

**Slow responses:**
```bash
# Check Redis
docker compose exec redis redis-cli ping

# Check Meilisearch
curl http://localhost:7700/health
```

## Rollback Procedure

```bash
# 1. Stop current version
docker compose down

# 2. Restore from backup
./scripts/backup/restore.sh backups/20240110_020000

# 3. Checkout previous version
git checkout v2.0.0

# 4. Start services
docker compose up -d

# 5. Verify
curl http://localhost:8000/api/health
```

## Performance Tuning

### Database Optimization

```bash
# Vacuum SQLite database
sqlite3 backend/auth.db "VACUUM;"

# Analyze query performance
sqlite3 backend/auth.db ".mode column" ".headers on" "EXPLAIN QUERY PLAN SELECT * FROM users;"
```

### Cache Tuning

```python
# Adjust cache settings in config.py
image_cache_ttl: int = 3600  # Increase for better performance
image_cache_max_size: int = 1000  # Increase for more caching
```

### Connection Pooling

```python
# Increase Odoo connection pool
_executor = ThreadPoolExecutor(max_workers=20)  # Increase from 10
```

## Compliance and Auditing

### Access Logs

```bash
# Enable detailed access logs
docker compose logs backend | grep "GET\|POST"

# Export for audit
docker compose logs --since 30d backend > audit-$(date +%Y%m).log
```

### Security Audit

```bash
# Run security scan
pip-audit
npm audit

# Check for outdated packages
pip list --outdated
npm outdated
```

## Resources

- [Docker Production Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [12-Factor App](https://12factor.net/)
- [Let's Encrypt](https://letsencrypt.org/)
- [Nginx Documentation](https://nginx.org/en/docs/)
