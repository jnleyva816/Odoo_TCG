# User Guide

This guide covers how to use TCG Inventory Management for daily operations.

## Getting Started

### Logging In

1. Open the application in your browser
2. Enter your username and password
3. Click "Sign In"

Your session will remain active for 24 hours. After that, you'll need to log in again.

## Scanner Page

The Scanner page is optimized for quickly adjusting inventory using a barcode scanner.

### Scanning Cards

1. Navigate to the Scanner page
2. Click in the search box (or it auto-focuses)
3. Scan a barcode or type a SKU
4. The card details appear
5. Use +/- buttons to adjust quantity

### Quick Actions

- **+1**: Add one to inventory
- **-1**: Remove one from inventory
- **Print Label**: Print a label for this card

### Keyboard Shortcuts

- `Enter`: After scanning, confirms the search
- Numbers can be typed directly for manual SKU entry

## Inventory Page

The Inventory page provides a comprehensive view of all products.

### Searching

Use the search box to find cards by:
- Card name
- SKU
- Set name

### Filtering

- **Stock Filter**: Show all, in stock only, or out of stock only
- **Set Filter**: Filter by specific card set

### Sorting

Click column headers to sort by:
- SKU
- Name
- Quantity
- Price

### Adjusting Stock

1. Find the card in the list
2. Click on the card row
3. Use +/- buttons in the modal
4. Changes save automatically

### Printing Labels

1. Click on a card
2. Click "Print Label" button
3. Label prints to the configured Brother QL printer

## Label Printing

### Label Contents

Each label includes:
- Card name
- Set name
- QR code (links to card on Collectr)
- EAN-13 barcode (scannable)
- SKU

### Printer Requirements

- Brother QL-700, QL-800, or compatible
- 29mm continuous tape
- Network connection to printer

### Troubleshooting Labels

**Label not printing:**
1. Check printer is on and connected
2. Verify printer IP in settings
3. Check if tape is loaded correctly

**Wrong font size:**
1. Ensure container has fonts installed
2. Check backend logs for "Could not load fonts" warnings

## Sets Page (Admin Feature)

The Sets page allows importing new card sets from TCGPlayer data.

> Note: This feature is disabled by default. Enable with `FEATURE_SETS_PAGE=true`

### Importing a Set

1. Navigate to Sets page
2. Search for a set (e.g., "Journey Together")
3. Click "Import"
4. Wait for import to complete

### Import Options

- **Skip Images**: Import card data without downloading images
- **Replace Existing**: Delete and re-import existing products

## Best Practices

### Daily Workflow

1. **Receiving New Cards**
   - Scan each card
   - Adjust quantity to match actual count
   - Print label for each card

2. **Shipping Orders**
   - Scan cards being shipped
   - Reduce quantity by amount shipped

3. **Inventory Counts**
   - Use the Inventory page
   - Filter to specific set
   - Compare quantities on screen to physical count
   - Adjust as needed

### Organization

- Print labels for all toploaders/sleeves
- Store cards in SKU order for easy finding
- Regular inventory audits

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `/` | Focus search box |
| `Esc` | Close modal |
| `Enter` | Confirm search |

## Mobile Usage

The app is fully responsive and works on mobile devices:

1. Open in mobile browser
2. Login as normal
3. Use Scanner page for quick scanning
4. All features work on mobile

For best results, bookmark the app to your home screen for quick access.

