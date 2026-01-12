# Premium Features

Two premium features are available via feature flags:

1. **Portfolio Dashboard** ("Wall Street" Analytics)
2. **Digital Vault** (Public Collection Showcase)

## Configuration

Enable in your `.env`:

```env
FEATURE_PORTFOLIO_DASHBOARD=true
FEATURE_PUBLIC_VAULT=true
```

---

## 1. Portfolio Dashboard

> "Your portfolio is up 12% this week"

Treat your card collection like a stock portfolio with financial-style analytics.

### Features

| Feature | Description |
|---------|-------------|
| **Portfolio Value** | Total value with 24h/7d/30d changes |
| **Top Movers** | Cards that gained/lost the most value |
| **Liquidity Breakdown** | Easy-to-sell vs. hard-to-sell assets |
| **Cost Basis Tracking** | Track what you paid vs. current value |
| **Unrealized P/L** | Calculate your profit before selling |

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/portfolio/stats` | GET | Pre-calculated portfolio summary |
| `/api/portfolio/top-movers` | GET | Top gainers/losers (24h) |
| `/api/portfolio/cost-basis` | GET | Cost basis entries |
| `/api/portfolio/cost-basis` | POST | Add cost basis entry |
| `/api/portfolio/refresh` | POST | Trigger manual refresh |

### Performance Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      HOW IT WORKS                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Scheduled Job (3 AM daily)                                  │
│     ├── Fetches all inventory from Odoo                         │
│     ├── Fetches price history from cache/API                    │
│     ├── Calculates portfolio stats                              │
│     └── Stores result in Redis as pre-cooked JSON               │
│                                                                 │
│  2. Dashboard Load (<20ms)                                      │
│     └── Fetches single pre-calculated row from Redis            │
│                                                                 │
│  3. Real-time Updates                                           │
│     └── Only cost basis tracking hits the database              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why this works:**
- No live calculations = no CPU spikes
- Pre-calculated data = instant load times
- Redis cache = sub-20ms response
- Scheduled job = consistent performance

### Liquidity Tiers

Cards are classified by how easy they are to sell:

| Tier | Sell Time | Examples |
|------|-----------|----------|
| **High** | < 24 hours | Meta cards, Charizards, chase cards |
| **Medium** | 1-7 days | Popular rares, playable cards |
| **Low** | 7-30 days | Niche promos, older sets |
| **Illiquid** | 30+ days | Bulk commons, damaged cards |

Classification is based on:
- Card rarity
- Set popularity
- Historical sales velocity
- Price point

### Cost Basis Tracking

Track your actual profit by recording purchase prices:

```json
POST /api/portfolio/cost-basis
{
  "product_id": 12345,
  "quantity": 10,
  "total_cost": 65.00,
  "purchase_date": "2024-01-15",
  "notes": "Bought lot at card show"
}
```

The dashboard then calculates:
- **Cost Per Unit**: $65 / 10 = $6.50 each
- **Current Value**: 10 × $12.00 = $120.00
- **Unrealized Profit**: $120 - $65 = $55.00

---

## 2. Digital Vault

> Share your collection without ugly spreadsheets

Create beautiful, shareable pages for your inventory.

### Features

| Feature | Description |
|---------|-------------|
| **Named Binders** | Organize cards (e.g., "High-End Trades") |
| **Public URLs** | Share link on Discord/Reddit |
| **Visitor Filtering** | Buyers can search/filter your cards |
| **Price Control** | Choose to show/hide prices |
| **View Tracking** | See how many people viewed |

### API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/vault/my-vaults` | GET | ✓ | List your vaults |
| `/api/vault/` | POST | ✓ | Create new vault |
| `/api/vault/{id}` | GET | ✓ | Get vault details |
| `/api/vault/{id}` | PUT | ✓ | Update vault |
| `/api/vault/{id}` | DELETE | ✓ | Delete vault |
| `/api/vault/{id}/publish` | POST | ✓ | Publish vault |
| `/api/vault/share/{id}` | GET | ✗ | Public view (no auth) |

### Visibility Levels

| Level | Description |
|-------|-------------|
| **Private** | Only you can see |
| **Unlisted** | Anyone with the link can see |
| **Public** | Listed in public directory |

### Performance Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    STATIC GENERATION                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. You click "Publish"                                         │
│     ├── Server generates static JSON snapshot                   │
│     ├── Caches in Redis (or uploads to CDN)                     │
│     └── Returns public URL                                      │
│                                                                 │
│  2. Visitor loads URL                                           │
│     └── Served directly from Redis/CDN                          │
│     └── Your Odoo server feels NOTHING                          │
│                                                                 │
│  3. 10,000 concurrent viewers?                                  │
│     └── No problem - it's just cached static data               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Why this works:**
- Static JSON = no database queries per visitor
- Redis/CDN cache = infinite scalability
- Snapshot on publish = consistent data

### Vault Settings

```json
{
  "show_prices": true,      // Show market prices
  "show_quantities": true,  // Show how many you have
  "allow_offers": false,    // Enable offer button
  "contact_method": "Discord: user#1234",
  "custom_message": "DM for bulk discounts!"
}
```

---

## Implementation Status

| Component | Status | Notes |
|-----------|--------|-------|
| Feature flags | ✅ Done | `FEATURE_PORTFOLIO_DASHBOARD`, `FEATURE_PUBLIC_VAULT` |
| Backend models | ✅ Done | `portfolio.py`, `vault.py` |
| API routers | ✅ Stubs | Endpoints defined, logic TODO |
| Frontend pages | ✅ Stubs | UI components ready |
| Redis caching | ⏳ TODO | Need to implement cache layer |
| Scheduled jobs | ⏳ TODO | Need Celery tasks for calculations |
| Static generation | ⏳ TODO | Need vault snapshot service |

---

## Future Enhancements

### Portfolio Dashboard
- [ ] Price alerts (notify when card crosses threshold)
- [ ] Historical charts (portfolio value over time)
- [ ] Set performance breakdown
- [ ] Export to CSV/PDF

### Digital Vault
- [ ] Custom themes/branding
- [ ] Embed widget for external sites
- [ ] QR code generation
- [ ] Offer/inquiry system
- [ ] Integration with eBay listings

