# Setup Guide

This guide covers setting up TCG Inventory Management for development and production.

## Prerequisites

### Required Software

- **Python 3.11+** - Backend runtime
- **Node.js 18+** - Frontend build tools
- **Docker & Docker Compose** - Container deployment
- **Git** - Version control

### Required Services

- **Odoo 16+** - ERP system with custom fields configured
- **PostgreSQL** - Odoo database (usually bundled with Odoo)

### Optional

- **Brother QL Label Printer** - For printing labels (QL-700, QL-800, etc.)

## Development Setup

### 1. Clone the Repository

```bash
git clone https://github.com/jnleyva816/Odoo_TCG.git
cd Odoo_TCG
```

### 2. Create Python Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
.\venv\Scripts\activate   # Windows
```

### 3. Install Dependencies

```bash
# Install CLI tools
pip install -e .

# Install backend
cd backend && pip install -e . && cd ..

# Install frontend
cd frontend && npm install && cd ..
```

### 4. Configure Environment

```bash
cp env.example .env
```

Edit `.env` with your settings:

```env
# Odoo Connection
ODOO_URL=http://192.168.10.105:8069
ODOO_DB=TCG-Cards
ODOO_USER=your-email@example.com
ODOO_PASSWORD=your-password

# Authentication
JWT_SECRET_KEY=your-secret-key-here
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD="your-secure-password"
```

Generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Start Development Servers

```bash
npm run dev
```

This starts:
- Frontend at http://localhost:5173
- Backend at http://localhost:8000

## Production Deployment (Docker)

### 1. Configure Environment

```bash
cd docker
cp ../env.example .env
# Edit .env with production values
```

### 2. Build and Start

```bash
docker compose up -d --build
```

### 3. Access the Application

- Frontend: http://your-server:3000
- API Docs: http://your-server:8000/docs

## Odoo Configuration

### Required Custom Fields

Add these fields to `product.product` model in Odoo:

| Field | Type | Label |
|-------|------|-------|
| `x_sku` | Char | TCGPlayer SKU |
| `x_rarity` | Char | Rarity |
| `x_set_name` | Char | Set Name |

### Create Product Category

Create a product category called "Pokemon Cards" (or similar) for organizing imported cards.

## Label Printer Setup

### Supported Printers

- Brother QL-700
- Brother QL-800
- Brother QL-810W
- Brother QL-820NWB

### Network Configuration

1. Connect printer to network (WiFi or Ethernet)
2. Note the printer's IP address
3. Configure in `.env`:

```env
PRINTER_ENABLED=true
PRINTER_IP=192.168.1.100
PRINTER_PORT=9100
PRINTER_MODEL=QL-800
PRINTER_LABEL_SIZE=29
```

### Label Size

Supported label sizes:
- `29` - 29mm (1.1") continuous tape
- `62` - 62mm (2.4") continuous tape

## Auto-Deploy Setup (NixOS)

See [DEPLOYMENT.md](DEPLOYMENT.md) for setting up automatic deployment with GitHub webhooks.

## Troubleshooting

### Backend won't start

1. Check if port 8000 is in use: `lsof -i :8000`
2. Verify Odoo connection in `.env`
3. Check logs: `docker compose logs backend`

### Frontend shows blank page

1. Check browser console for errors
2. Verify API is running at http://localhost:8000/api/health
3. Check CORS settings in backend config

### Labels not printing

1. Verify printer IP is correct
2. Check printer is on and connected to network
3. Test connection: `ping PRINTER_IP`
4. Check backend logs for errors

### Login fails

1. Verify admin credentials in `.env`
2. Check if database was initialized: look for "Admin user created" in logs
3. Clear browser cache and try again

