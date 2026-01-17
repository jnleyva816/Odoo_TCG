# Production Deployment Guide

## Overview

This guide provides comprehensive instructions for deploying the Odoo TCG Inventory Management System to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Security Hardening](#security-hardening)
4. [Database Setup](#database-setup)
5. [Application Deployment](#application-deployment)
6. [Monitoring & Logging](#monitoring--logging)
7. [Backup & Recovery](#backup--recovery)
8. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### System Requirements

**Minimum:**
- 2 vCPU
- 4 GB RAM
- 50 GB SSD storage
- Ubuntu 22.04 LTS or similar

**Recommended:**
- 4 vCPU
- 8 GB RAM
- 100 GB SSD storage
- Ubuntu 22.04 LTS

### Software Requirements

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install nginx (reverse proxy)
sudo apt install nginx certbot python3-certbot-nginx -y

# Install monitoring tools
sudo apt install htop iotop nethogs -y
```

---

## Infrastructure Setup

### 1. Domain & DNS Configuration

**DNS Records:**

```
# A Records
inventory.example.com    -> <server-ip>

# Optional: CDN
cdn.example.com          -> <cdn-provider>
```

### 2. Firewall Configuration

```bash
# UFW (Ubuntu Firewall)
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change 22 to your custom port if modified)
sudo ufw allow 22/tcp

# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Enable firewall
sudo ufw enable
sudo ufw status verbose
```

### 3. Nginx Reverse Proxy

```nginx
# /etc/nginx/sites-available/tcg-inventory
upstream backend {
    # Multiple backend instances for load balancing
    server localhost:8000 max_fails=3 fail_timeout=30s;
    # server localhost:8001 max_fails=3 fail_timeout=30s;  # Add more as needed
}

upstream frontend {
    server localhost:3000 max_fails=3 fail_timeout=30s;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name inventory.example.com;
    
    # ACME challenge for Let's Encrypt
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    # Redirect all other traffic to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name inventory.example.com;
    
    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/inventory.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/inventory.example.com/privkey.pem;
    ssl_trusted_certificate /etc/letsencrypt/live/inventory.example.com/chain.pem;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers 'ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384';
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_session_tickets off;
    
    # OCSP Stapling
    ssl_stapling on;
    ssl_stapling_verify on;
    resolver 8.8.8.8 8.8.4.4 valid=300s;
    resolver_timeout 5s;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    
    # Logging
    access_log /var/log/nginx/tcg-access.log;
    error_log /var/log/nginx/tcg-error.log;
    
    # Gzip Compression
    gzip on;
    gzip_vary on;
    gzip_comp_level 6;
    gzip_types text/plain text/css text/xml text/javascript application/json application/javascript application/xml+rss application/rss+xml font/truetype font/opentype application/vnd.ms-fontobject image/svg+xml;
    
    # Frontend (React)
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (for future real-time features)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
    
    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffer settings
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
        proxy_busy_buffers_size 8k;
    }
    
    # API Documentation
    location /docs {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Static assets with caching
    location ~* \.(jpg|jpeg|png|gif|ico|css|js|svg|woff|woff2|ttf|eot)$ {
        proxy_pass http://frontend;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check endpoint (bypass caching)
    location = /api/health {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        access_log off;
    }
}
```

**Enable site:**

```bash
# Create symbolic link
sudo ln -s /etc/nginx/sites-available/tcg-inventory /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

### 4. SSL Certificate

```bash
# Obtain certificate
sudo certbot --nginx -d inventory.example.com

# Auto-renewal (cron job)
sudo crontab -e

# Add line:
0 0 * * 0 certbot renew --quiet --deploy-hook "systemctl reload nginx"
```

---

## Security Hardening

### 1. SSH Hardening

```bash
# /etc/ssh/sshd_config
sudo nano /etc/ssh/sshd_config

# Recommended settings:
Port 2222  # Change from default 22
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2

# Restart SSH
sudo systemctl restart sshd
```

### 2. Fail2Ban

```bash
# Install Fail2Ban
sudo apt install fail2ban -y

# Configure
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
sudo nano /etc/fail2ban/jail.local

# Add nginx jail
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/tcg-error.log

[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/tcg-error.log

# Start Fail2Ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 3. System Hardening

```bash
# Disable unused services
sudo systemctl disable bluetooth
sudo systemctl disable cups

# Set up automatic security updates
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure --priority=low unattended-upgrades

# Install intrusion detection
sudo apt install aide -y
sudo aideinit
```

---

## Database Setup

### 1. PostgreSQL for Auth Database (Optional Upgrade)

```bash
# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Create database and user
sudo -u postgres psql

CREATE DATABASE tcg_auth;
CREATE USER tcg_user WITH ENCRYPTED PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE tcg_auth TO tcg_user;
\q

# Update connection string in .env
# DATABASE_URL=postgresql://tcg_user:secure-password@localhost:5432/tcg_auth
```

### 2. Redis Configuration

```bash
# Redis production config
sudo nano /etc/redis/redis.conf

# Key settings:
maxmemory 2gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
requirepass your-redis-password

# Restart Redis
sudo systemctl restart redis
```

---

## Application Deployment

### 1. Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/tcg-inventory
sudo chown $USER:$USER /opt/tcg-inventory

# Clone repository
cd /opt/tcg-inventory
git clone https://github.com/jnleyva816/Odoo_TCG.git .
```

### 2. Configure Environment

```bash
# Create production .env
cp env.example .env
nano .env

# Production settings:
# ==================
# Server
DEBUG=false
SERVER_HOST=0.0.0.0
SERVER_PORT=8000

# Odoo
ODOO_URL=https://your-odoo-server.com
ODOO_DB=production-db
ODOO_USER=api_user
ODOO_PASSWORD=<secure-password>

# Authentication
JWT_SECRET_KEY=<generate with: openssl rand -hex 32>
JWT_EXPIRE_MINUTES=15  # Short-lived for security

# Redis
REDIS_URL=redis://:your-redis-password@localhost:6379/0

# Meilisearch
MEILI_URL=http://localhost:7700
MEILI_MASTER_KEY=<secure-key>

# Security
CORS_ORIGINS=["https://inventory.example.com"]

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# Email Alerts
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=alerts@example.com
SMTP_PASSWORD=<app-password>
ALERT_EMAIL=admin@example.com
```

### 3. Deploy with Docker Compose

```bash
# Navigate to docker directory
cd /opt/tcg-inventory/docker

# Copy environment
cp ../.env .

# Build and start services
docker compose up -d --build

# View logs
docker compose logs -f
```

### 4. Initialize Data

```bash
# Run database migrations
docker compose exec backend python -m alembic upgrade head

# Create admin user
docker compose exec backend python -m app.scripts.create_admin

# Warm cache
docker compose exec backend python -m app.tasks.warm_cache
```

---

## Monitoring & Logging

### 1. Application Logs

```bash
# View all logs
docker compose logs -f

# View specific service
docker compose logs -f backend

# Follow logs with timestamps
docker compose logs -f -t --tail=100 backend
```

### 2. System Monitoring

```bash
# Install monitoring tools
sudo apt install prometheus prometheus-node-exporter grafana -y

# Configure Prometheus
sudo nano /etc/prometheus/prometheus.yml

# Add job:
scrape_configs:
  - job_name: 'tcg-backend'
    static_configs:
      - targets: ['localhost:8000']
```

### 3. Log Aggregation (ELK Stack - Optional)

```bash
# Install Elasticsearch, Logstash, Kibana
# See: https://www.elastic.co/guide/en/elastic-stack/current/installing-elastic-stack.html
```

### 4. Uptime Monitoring

```bash
# UptimeRobot (external service)
# Add monitors for:
# - https://inventory.example.com
# - https://inventory.example.com/api/health
```

---

## Backup & Recovery

### 1. Automated Backups

```bash
# Create backup script
sudo nano /usr/local/bin/tcg-backup.sh

#!/bin/bash
# TCG Inventory Backup Script

BACKUP_DIR="/var/backups/tcg-inventory"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Backup Docker volumes
docker run --rm \
  -v tcg_redis-data:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/redis-$DATE.tar.gz -C /data .

docker run --rm \
  -v tcg_meili-data:/data \
  -v $BACKUP_DIR:/backup \
  alpine tar czf /backup/meili-$DATE.tar.gz -C /data .

# Backup application data
tar czf $BACKUP_DIR/app-$DATE.tar.gz /opt/tcg-inventory

# Backup auth database
docker compose exec -T backend \
  sqlite3 auth.db .dump > $BACKUP_DIR/auth-$DATE.sql

# Delete backups older than 30 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete

echo "Backup completed: $DATE"

# Make executable
sudo chmod +x /usr/local/bin/tcg-backup.sh

# Add to cron (daily at 2 AM)
sudo crontab -e
0 2 * * * /usr/local/bin/tcg-backup.sh >> /var/log/tcg-backup.log 2>&1
```

### 2. Disaster Recovery

```bash
# Stop services
cd /opt/tcg-inventory/docker
docker compose down

# Restore Redis
docker run --rm \
  -v tcg_redis-data:/data \
  -v /var/backups/tcg-inventory:/backup \
  alpine tar xzf /backup/redis-20240101_020000.tar.gz -C /data

# Restore Meilisearch
docker run --rm \
  -v tcg_meili-data:/data \
  -v /var/backups/tcg-inventory:/backup \
  alpine tar xzf /backup/meili-20240101_020000.tar.gz -C /data

# Restore auth database
docker compose up -d backend
docker compose exec -T backend sqlite3 auth.db < /var/backups/tcg-inventory/auth-20240101_020000.sql

# Start all services
docker compose up -d
```

---

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check service status
docker compose ps

# Check logs for errors
docker compose logs backend

# Common fixes:
# - Check .env file configuration
# - Verify Odoo connection
# - Check Redis/Meilisearch availability
```

#### 2. High Memory Usage

```bash
# Check memory usage
free -h
docker stats

# Increase Redis maxmemory
sudo nano /etc/redis/redis.conf
# maxmemory 4gb

# Restart Redis
sudo systemctl restart redis
```

#### 3. Slow Performance

```bash
# Check system resources
htop
iotop
nethogs

# Check application metrics
curl http://localhost:8000/api/metrics/performance

# Common fixes:
# - Increase cache TTL
# - Add more backend instances
# - Optimize Odoo queries
```

#### 4. Connection Refused

```bash
# Check nginx status
sudo systemctl status nginx

# Check firewall
sudo ufw status

# Check SSL certificate
sudo certbot certificates

# Test backend directly
curl http://localhost:8000/api/health
```

### Debug Mode

```bash
# Enable debug mode temporarily
docker compose exec backend /bin/bash
export DEBUG=true
uvicorn app.main:app --reload

# View detailed logs
tail -f /var/log/nginx/tcg-error.log
```

---

## Performance Tuning

### 1. Nginx Optimization

```nginx
# /etc/nginx/nginx.conf
worker_processes auto;
worker_rlimit_nofile 65535;

events {
    worker_connections 4096;
    use epoll;
    multi_accept on;
}

http {
    sendfile on;
    tcp_nopush on;
    tcp_nodelay on;
    
    # Connection pooling
    keepalive_timeout 65;
    keepalive_requests 100;
    
    # Client body size
    client_max_body_size 10M;
}
```

### 2. System Limits

```bash
# /etc/security/limits.conf
* soft nofile 65535
* hard nofile 65535

# /etc/sysctl.conf
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 8192
net.ipv4.tcp_tw_reuse = 1
```

### 3. Docker Resource Limits

```yaml
# docker-compose.yml
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

---

## Scaling Strategies

### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  backend:
    scale: 3  # Run 3 backend instances
```

**Nginx load balancing:**

```nginx
upstream backend {
    least_conn;  # or ip_hash for sticky sessions
    server localhost:8000;
    server localhost:8001;
    server localhost:8002;
}
```

### Vertical Scaling

- Increase server resources (CPU, RAM)
- Optimize Redis memory
- Tune PostgreSQL settings

---

## Maintenance Windows

### Planned Maintenance

```bash
# Set maintenance mode
docker compose exec backend python -m app.scripts.maintenance on

# Perform updates
git pull origin main
docker compose up -d --build

# Exit maintenance mode
docker compose exec backend python -m app.scripts.maintenance off
```

---

## Security Audit Checklist

- [ ] SSL certificate valid and auto-renewing
- [ ] Firewall configured (UFW/iptables)
- [ ] SSH hardened (key auth only, custom port)
- [ ] Fail2Ban installed and configured
- [ ] Security headers configured in nginx
- [ ] Secrets rotated (JWT, Redis, Meilisearch)
- [ ] Backups tested and working
- [ ] Monitoring and alerting configured
- [ ] Logs reviewed regularly
- [ ] Dependencies updated (security patches)

---

## Post-Deployment Verification

```bash
# 1. Health checks
curl https://inventory.example.com/api/health
curl https://inventory.example.com/api/health/ready

# 2. SSL check
curl -I https://inventory.example.com | grep -i strict

# 3. Performance test
ab -n 1000 -c 10 https://inventory.example.com/api/health

# 4. Security scan
nmap -sV inventory.example.com
```

---

## References

- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [Docker Compose Production](https://docs.docker.com/compose/production/)
- [Nginx Security Best Practices](https://www.nginx.com/blog/mitigating-ddos-attacks-with-nginx-and-nginx-plus/)
- [Let's Encrypt Best Practices](https://letsencrypt.org/docs/)
