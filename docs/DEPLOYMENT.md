# Deployment Guide

This guide covers deploying TCG Inventory Management to a production server with automatic deployments.

## Docker Deployment

### Prerequisites

- Docker 20.10+
- Docker Compose v2+
- Git

### Steps

1. **Clone the repository**

```bash
git clone https://github.com/jnleyva816/Odoo_TCG.git /opt/Odoo_TCG
cd /opt/Odoo_TCG
```

2. **Configure environment**

```bash
cd docker
cp ../env.example .env
nano .env  # Edit with production values
```

3. **Build and start containers**

```bash
docker compose up -d --build
```

4. **Verify deployment**

```bash
docker compose ps
curl http://localhost:8000/api/health
```

### Container Management

```bash
# View logs
docker compose logs -f

# Restart services
docker compose restart

# Stop services
docker compose down

# Rebuild and restart
docker compose up -d --build
```

## Auto-Deploy with GitHub Webhooks

Set up automatic deployment when you push to GitHub.

### 1. Generate Webhook Secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Save this secret - you'll need it for GitHub and the server.

### 2. Configure Webhook Service (NixOS)

Add to `/etc/nixos/configuration.nix`:

```nix
systemd.services.tcg-autodeploy = {
  description = "TCG Auto-Deploy Webhook Server";
  after = [ "network.target" "docker.service" ];
  wantedBy = [ "multi-user.target" ];
  path = [ pkgs.git pkgs.docker ];
  environment = {
    WEBHOOK_SECRET = "your-webhook-secret-here";
    PYTHONUNBUFFERED = "1";
  };
  serviceConfig = {
    Type = "simple";
    User = "root";
    WorkingDirectory = "/opt/Odoo_TCG";
    ExecStart = "${pkgs.python3}/bin/python3 /opt/Odoo_TCG/scripts/deploy-webhook.py";
    Restart = "always";
    RestartSec = 10;
    StandardOutput = "journal";
    StandardError = "journal";
  };
};

# Open firewall port
networking.firewall.allowedTCPPorts = [ 9000 ];
```

Apply configuration:

```bash
nixos-rebuild switch
```

### 3. Configure GitHub Webhook

1. Go to your repository Settings → Webhooks
2. Click "Add webhook"
3. Configure:
   - **Payload URL**: `http://your-server-ip:9000/deploy`
   - **Content type**: `application/json`
   - **Secret**: Your webhook secret
   - **Events**: Just the push event
   - **Active**: Checked

4. Click "Add webhook"

### 4. Test Auto-Deploy

Push a commit and check the logs:

```bash
journalctl -u tcg-autodeploy -f
```

## SSL/HTTPS Setup

### Option 1: Cloudflare Tunnel (Recommended)

1. Sign up for Cloudflare (free)
2. Add your domain
3. Install cloudflared
4. Create a tunnel pointing to your local ports

### Option 2: Nginx Reverse Proxy with Let's Encrypt

1. Install Certbot
2. Configure Nginx as reverse proxy
3. Obtain SSL certificate

Example Nginx config:

```nginx
server {
    listen 443 ssl;
    server_name tcg.yourdomain.com;
    
    ssl_certificate /etc/letsencrypt/live/tcg.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/tcg.yourdomain.com/privkey.pem;
    
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
    }
    
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
    }
}
```

## Monitoring

### View Container Status

```bash
docker compose ps
```

### View Logs

```bash
# All services
docker compose logs -f

# Specific service
docker compose logs backend -f
docker compose logs frontend -f
```

### Health Check

```bash
curl http://localhost:8000/api/health
```

### Check Disk Usage

```bash
docker system df
```

### Cleanup Old Images

```bash
docker image prune -a
```

## Backup

### Database Backup

The auth database is stored in a Docker volume. To backup:

```bash
docker compose exec backend cat /data/auth.db > auth_backup.db
```

### Configuration Backup

```bash
cp docker/.env docker/.env.backup
```

## Updating

### Manual Update

```bash
cd /opt/Odoo_TCG
git pull
cd docker
docker compose up -d --build
```

### With Auto-Deploy

Just push to GitHub - the webhook will handle the rest!

