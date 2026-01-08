# TCG Automation - Docker Deployment

## Quick Start (Local/Proxmox)

### 1. Clone the repo on your Proxmox server

```bash
ssh your-proxmox-server
cd /opt  # or wherever you want to deploy
git clone https://github.com/jnleyva816/Odoo_TCG.git
cd Odoo_TCG
```

### 2. Create your `.env` file with credentials

```bash
cp env.example .env
nano .env  # Edit with your real credentials
```

Edit the `.env` file:
```env
ODOO_URL=http://192.168.10.105:8069
ODOO_DB=TCG-Cards
ODOO_USER=your-real-email@example.com
ODOO_PASSWORD=your-real-password

PRINTER_ENABLED=true
PRINTER_IP=192.168.10.104
```

### 3. Build and start the containers

```bash
cd docker
docker compose up -d --build
```

### 4. Verify it's running

```bash
# Check containers
docker compose ps

# Check logs
docker compose logs -f backend

# Test API
curl http://localhost:8000/api/health
```

---

## Services

| Service | Port | Description |
|---------|------|-------------|
| **frontend** | 3000 | React web UI |
| **backend** | 8000 | FastAPI REST API |

---

## Commands

### Start all services
```bash
docker compose up -d
```

### Stop all services
```bash
docker compose down
```

### Rebuild after code changes
```bash
git pull
docker compose up -d --build
```

### View logs
```bash
docker compose logs -f          # All services
docker compose logs -f backend  # Just backend
```

### Run CLI commands
```bash
docker compose run --rm tcg-cli status
docker compose run --rm tcg-cli barcodes verify
docker compose run --rm tcg-cli sync
```

---

## Updating

To update to the latest version:

```bash
cd /opt/Odoo_TCG  # or wherever you cloned it
git pull
cd docker
docker compose up -d --build
```

---

## Troubleshooting

### Backend won't connect to Odoo
- Check `ODOO_URL` is reachable from the container
- Verify credentials in `.env`
- Check Odoo is running: `curl http://192.168.10.105:8069`

### Port already in use
```bash
# Find what's using the port
lsof -i :8000

# Use different ports in docker-compose.yml
ports:
  - "8080:8000"  # Map to 8080 instead
```

### View container logs
```bash
docker compose logs backend
```


