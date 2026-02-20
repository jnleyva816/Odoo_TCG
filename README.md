# TCG Inventory Management

A full-stack Pokemon TCG card inventory management system with Odoo ERP integration. Features a modern React frontend, FastAPI backend, JWT authentication, and automated deployment.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![React](https://img.shields.io/badge/react-18+-61DAFB.svg)

## Features

- 🔐 **Odoo Authentication** - Login with your Odoo credentials, JWT tokens for API
- 📦 **Inventory Management** - Track card quantities, prices, and stock levels
- 🔍 **Instant Search** - Meilisearch-powered typo-tolerant card search
- 🔍 **Barcode Scanner** - Scan cards to quickly adjust inventory
- 🏷️ **Label Printing** - Generate and print labels for Brother QL printers
- 🔄 **Odoo Integration** - Full sync with Odoo ERP for inventory and products
- ⚡ **Redis Caching** - Fast response times with Redis-backed caching & rate limiting
- 🚀 **Auto-Deploy** - Push to GitHub and auto-deploy to your server
- 🎛️ **Feature Flags** - Enable/disable features via environment variables

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (includes Redis & Meilisearch)
- Odoo 16+ instance (for data storage and authentication)
- (Optional) Brother QL label printer

### Local Development

```bash
# Clone the repository
git clone https://github.com/jnleyva816/Odoo_TCG.git
cd Odoo_TCG

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: .\venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
cd backend && pip install -e . && cd ..
cd frontend && npm install && cd ..

# Configure environment
cp env.example .env
# Edit .env with your credentials

# Start development servers
npm run dev
```

Then open http://localhost:5173 in your browser.

### Docker Deployment

```bash
cd docker

# Copy and configure environment
cp ../env.example .env
# Edit .env with your credentials

# Build and start
docker compose up -d --build

# View logs
docker compose logs -f
```

Access the app at http://localhost:3000

## Configuration

Create a `.env` file based on `env.example`:

```env
# Odoo Connection (users login with their Odoo credentials)
ODOO_URL=http://your-odoo-server:8069
ODOO_DB=your-database

# JWT Token Signing (REQUIRED - generate with: openssl rand -hex 32)
JWT_SECRET_KEY=your-secret-key-here
JWT_EXPIRE_MINUTES=1440  # 24 hours

# Redis (caching & rate limiting)
REDIS_URL=redis://localhost:6379/0

# Meilisearch (instant search)
MEILI_URL=http://localhost:7700
MEILI_MASTER_KEY=your-meili-key

# Feature Flags
FEATURE_SCANNER_PAGE=true
FEATURE_INVENTORY_PAGE=true
FEATURE_SETS_PAGE=false
FEATURE_LABEL_PRINTING=true

# Label Printer (Optional)
PRINTER_ENABLED=true
PRINTER_IP=192.168.1.100
PRINTER_PORT=9100
PRINTER_MODEL=QL-800
PRINTER_LABEL_SIZE=29
```

> **Note:** Users log in with their existing **Odoo credentials**. No separate user management needed!

### Feature Flags

Control which features are available:

| Flag | Default | Description |
|------|---------|-------------|
| `FEATURE_SCANNER_PAGE` | `true` | Barcode scanner for quick inventory |
| `FEATURE_INVENTORY_PAGE` | `true` | Full inventory management |
| `FEATURE_SETS_PAGE` | `false` | Card set import (admin feature) |
| `FEATURE_LABEL_PRINTING` | `true` | Brother QL label printing |
| `FEATURE_PORTFOLIO_DASHBOARD` | `false` | "Wall Street" portfolio analytics |
| `FEATURE_PUBLIC_VAULT` | `false` | "Digital Vault" public showcase |

See [Premium Features](docs/reference/PREMIUM_FEATURES.md) for details on Portfolio Dashboard and Digital Vault.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   React App     │────▶│  FastAPI Backend │────▶│   Odoo ERP      │
│   (Frontend)    │     │   (REST API)     │     │ (Data + Auth)   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
              ▼                ▼                ▼
       ┌────────────┐   ┌────────────┐   ┌────────────┐
       │   Redis    │   │ Meilisearch│   │   Celery   │
       │  (Cache &  │   │  (Search)  │   │  (Tasks)   │
       │Rate Limit) │   │            │   │            │
       └────────────┘   └────────────┘   └────────────┘
```

### How Authentication Works

1. User enters **Odoo credentials** (email/password)
2. Backend validates credentials against **Odoo XML-RPC**
3. On success, backend issues a **JWT token** (24h expiry)
4. Frontend stores token and sends it with all API requests
5. No separate user database - **Odoo is the source of truth**

## Project Structure

```
Odoo_TCG/
├── backend/                 # FastAPI backend
│   └── app/
│       ├── auth/           # JWT authentication
│       ├── middleware/     # Security, rate limiting, tracing
│       ├── routers/        # API endpoints
│       ├── services/       # Business logic
│       └── utils/          # Validators, logging
├── frontend/               # React frontend
│   └── src/
│       ├── contexts/       # Auth & Features contexts
│       ├── pages/          # Page components
│       └── components/     # Shared components
├── docker/                 # Docker configuration
├── scripts/                # Utility scripts
│   ├── backup/            # Backup & restore
│   ├── data/              # CSV import, image fixes
│   ├── deploy/            # Auto-deploy webhook
│   ├── maintenance/       # Price sync, warehouse setup
│   └── server/            # Dev server startup
├── src/tcg_automation/     # CLI tools
└── docs/                   # Documentation
    ├── guides/            # Setup, deployment, operations
    ├── reference/         # API, testing docs
    └── archive/           # Historical reports
```

## API Documentation

When running, access interactive API docs at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | Login with Odoo credentials, get JWT |
| `/api/auth/me` | GET | Get current user info |
| `/api/cards/search` | GET | Search cards (Meilisearch-powered) |
| `/api/inventory/` | GET | Get inventory with filters |
| `/api/inventory/adjust` | POST | Adjust stock quantity |
| `/api/labels/print/{id}` | POST | Print label for product |
| `/api/features` | GET | Get enabled feature flags |
| `/api/health` | GET | Liveness check |
| `/api/health/ready` | GET | Readiness check (verifies Odoo connection) |

## CLI Commands

```bash
# Check Odoo connection
tcg status

# Import a card set
tcg import sv09

# Sync prices from TCGPlayer
tcg sync

# Generate labels
tcg labels sv09-001 sv09-002

# Backfill barcodes
tcg barcodes backfill
```

## Auto-Deploy (NixOS/Proxmox)

The project includes a webhook-based auto-deploy system:

1. Push to GitHub
2. GitHub sends webhook to your server
3. Server pulls latest code
4. Docker containers rebuild automatically

See `scripts/deploy-webhook.py` for the webhook server configuration.

## Development

### Backend

```bash
cd backend
pip install -e ".[dev]"

# Run linter
ruff check .

# Run type checker
mypy .

# Run tests
pytest tests/ -v
```

### Frontend

```bash
cd frontend
npm install

# Run dev server
npm run dev

# Type check
npm run type-check

# Build for production
npm run build
```

## Security

- **Odoo-based authentication** - Users login with existing Odoo credentials
- **JWT tokens** expire after 24 hours (configurable)
- **Redis-backed rate limiting** - 60 req/min, 10 req/5s burst (distributed)
- **OWASP-compliant security headers** - HSTS, CSP, X-Frame-Options, etc.
- **Input validation and sanitization** - XSS and injection prevention
- **Request ID tracing** - End-to-end request tracking for debugging
- **Audit logging** - Login attempts and security events logged

See [SECURITY.md](SECURITY.md) for security policy and vulnerability reporting.

## Documentation

See [docs/README.md](docs/README.md) for the full documentation index.

### Quick Links

- **[Setup Guide](docs/guides/SETUP.md)** - Getting started
- **[API Reference](docs/reference/API.md)** - Endpoints and examples
- **[Production Guide](docs/guides/PRODUCTION.md)** - Deployment best practices
- **[Backup & Restore](docs/guides/BACKUP.md)** - Disaster recovery
- **[Testing Guide](docs/reference/TESTING.md)** - Testing strategies
- **[Contributing](CONTRIBUTING.md)** - How to contribute

## Roadmap

- [x] Card import from tcgcsv.com
- [x] Price sync automation
- [x] Label generation & scanner
- [x] Odoo-based authentication (login with Odoo credentials)
- [x] Meilisearch instant search
- [x] Redis caching & distributed rate limiting
- [x] Docker deployment
- [x] Auto-deploy with webhooks
- [x] Feature flags
- [x] Security enhancements (OWASP compliance)
- [x] Production-ready monitoring
- [x] Comprehensive documentation
- [~] **Portfolio Dashboard** - "Wall Street" analytics (scaffolding done)
- [~] **Digital Vault** - Public collection showcase (scaffolding done)
- [ ] eBay auto-listing
- [ ] eBay order import
- [ ] Mobile app (PWA support added)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Josh Leyva (joshleyva816@gmail.com)
