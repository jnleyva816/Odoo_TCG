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

This section covers setting up Odoo 16+ to work with TCG Inventory Management.

### Installing Odoo

#### Option 1: Docker (Recommended for Testing)

```bash
# Create docker-compose.yml for Odoo
cat > odoo-docker-compose.yml << 'EOF'
services:
  odoo:
    image: odoo:16
    depends_on:
      - db
    ports:
      - "8069:8069"
    volumes:
      - odoo-data:/var/lib/odoo
      - ./odoo-addons:/mnt/extra-addons
    environment:
      - HOST=db
      - USER=odoo
      - PASSWORD=odoo

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=postgres
      - POSTGRES_PASSWORD=odoo
      - POSTGRES_USER=odoo
    volumes:
      - postgres-data:/var/lib/postgresql/data

volumes:
  odoo-data:
  postgres-data:
EOF

# Start Odoo
docker compose -f odoo-docker-compose.yml up -d
```

Access Odoo at http://localhost:8069

#### Option 2: Native Installation

Follow the [official Odoo installation guide](https://www.odoo.com/documentation/16.0/administration/install.html).

### Initial Odoo Setup

1. **Create Database**
   - Navigate to http://localhost:8069
   - Fill in the database creation form:
     - **Database Name**: `TCG-Cards` (or your preference)
     - **Email**: Your admin email
     - **Password**: Your admin password
     - **Language**: English
     - **Country**: Your country
   - Click "Create Database"

2. **Install Required Apps**
   - Go to Apps menu
   - Search and install:
     - **Inventory** (stock management)
     - **Sales** (for pricing)
     - **Purchase** (optional, for cost tracking)

### Creating Custom Fields

TCG Inventory requires custom fields on products to store card-specific data.

#### Step 1: Enable Developer Mode

1. Go to **Settings** → **General Settings**
2. Scroll to the bottom
3. Click **Activate the developer mode**

#### Step 2: Add Custom Fields

1. Go to **Settings** → **Technical** → **Models**
2. Search for `product.product`
3. Click on it to open
4. Go to the **Fields** tab
5. Click **Add a line** for each field:

| Field Name | Field Label | Field Type | Notes |
|------------|-------------|------------|-------|
| `x_sku` | TCGPlayer SKU | Char | Store original TCGPlayer SKU |
| `x_rarity` | Rarity | Char | Card rarity (Common, Rare, etc.) |
| `x_set_name` | Set Name | Char | Pokemon set name |
| `x_tcgplayer_id` | TCGPlayer ID | Integer | Optional: TCGPlayer product ID |

#### Alternative: Using Odoo Studio (Enterprise)

If you have Odoo Enterprise with Studio:

1. Go to **Inventory** → **Products**
2. Open any product
3. Click the **Studio** icon (paintbrush)
4. Drag **Text** fields onto the form
5. Configure each field with the names above
6. Click **Close**

### Product Category Setup

1. Go to **Inventory** → **Configuration** → **Product Categories**
2. Click **Create**
3. Fill in:
   - **Name**: `Pokemon Cards`
   - **Parent Category**: `All` (or your preference)
   - **Costing Method**: `Standard Price`
   - **Inventory Valuation**: `Manual` (or `Automated` if tracking costs)
4. Click **Save**

### Configure Product Defaults

To make importing easier, set up default values:

1. Go to **Inventory** → **Configuration** → **Settings**
2. Under **Products**:
   - Enable **Variants** if you want to track holofoil/reverse variants
   - Set default **Unit of Measure** to `Units`

### API Access Setup

The TCG application connects via XML-RPC. Ensure your Odoo user has proper permissions:

1. Go to **Settings** → **Users & Companies** → **Users**
2. Click on your user
3. Under **Access Rights**, ensure you have:
   - **Inventory**: `Administrator` or `User`
   - **Sales**: `User` or higher
4. Note your **Login** (email) for the `.env` file

### Testing the Connection

After configuring Odoo:

```bash
# Test connection with CLI
tcg status
```

Expected output:
```
✅ Connected to Odoo at http://localhost:8069
   Database: TCG-Cards
   User: admin@example.com
   Products: 0
```

### Odoo Configuration Reference

Your `.env` file should have:

```env
# Odoo Connection
ODOO_URL=http://localhost:8069      # Your Odoo server URL
ODOO_DB=TCG-Cards                   # Database name you created
ODOO_USER=admin@example.com         # Your Odoo login email
ODOO_PASSWORD=your-password         # Your Odoo password
```

### Troubleshooting Odoo

#### "Invalid database" error

- Verify `ODOO_DB` matches exactly (case-sensitive)
- Check database exists: Odoo login page shows available databases

#### "Access Denied" error

- Verify email and password are correct
- Check user has Inventory permissions
- Ensure API access is not blocked by firewall

#### Custom fields not found

- Verify fields are created on `product.product` (not `product.template`)
- Field names must start with `x_` prefix
- Restart Odoo after adding fields: `docker compose restart odoo`

#### Products not showing

- Ensure products are marked as **Storable Product** (not Service)
- Check product is **Active** (not archived)
- Verify user has access to the product's company

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

