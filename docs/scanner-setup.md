# Pokemon Card Scanner Setup Guide

This guide walks you through setting up the ML-based card scanner system.

## Architecture Overview

The scanner uses a **two-stage approach**:

1. **Stage 1 - Detection (YOLO)**: A YOLOv8 model finds card bounding boxes in images
2. **Stage 2 - Identification (pHash)**: Perceptual hashing matches cropped cards against Odoo products

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│   Webcam/   │ --> │  YOLO Model  │ --> │  Hash Matcher │ --> Odoo Product
│   Image     │     │  (Detection) │     │   (Identify)  │
└─────────────┘     └──────────────┘     └───────────────┘
                           │                     │
                    ONNX Runtime            Odoo x_phash
                    (CPU optimized)         (existing field)
```

**No separate database needed** - hashes are stored directly on Odoo products in the `x_phash` field.

## Prerequisites

- Python 3.11+
- Node.js 18+ (for frontend)
- Odoo with `x_phash` custom field on products (already configured)
- A GPU workstation or Kaggle account (for YOLO training only)

## Quick Start

### 1. Install Backend Dependencies

```bash
cd backend
pip install -e .
```

This installs the scanner dependencies:
- `onnxruntime` - ONNX model inference
- `imagehash` - Perceptual hashing
- `opencv-python-headless` - Image processing

### 2. Verify Hash Data

Your Odoo products already have `x_phash` populated. Check status:

```bash
# Via psql
PGPASSWORD=odoo psql -h YOUR_HOST -U odoo -d "TCG-Cards" -c \
  "SELECT COUNT(*) as total, COUNT(x_phash) as with_hash FROM product_template;"
```

If any products are missing hashes, populate them:

```bash
cd scripts

# Dry run first
python populate_phash.py --dry-run

# Actually populate
python populate_phash.py

# Only specific set
python populate_phash.py --set "SV10: Destined Rivals"
```

### 3. Train the YOLO Model

You have two options:

**Option A: Kaggle Notebook (Free GPU)**

1. Open `ml/kaggle_notebook.ipynb` in Kaggle
2. Connect your Roboflow dataset
3. Run all cells
4. Download `pokemon_card_detector.onnx`

**Option B: Local Training (Requires GPU)**

```bash
cd ml

# Train
python train_yolo.py train --data ./data/roboflow/data.yaml --epochs 100

# Export to ONNX
python train_yolo.py export --weights ./runs/detect/pokemon_card_detector/weights/best.pt
```

### 4. Deploy the Model

Copy the ONNX model to the backend:

```bash
cp ml/runs/detect/pokemon_card_detector/weights/best.onnx \
   backend/app/models/scanner/pokemon_card_detector.onnx
```

### 5. Configure (Optional)

Scanner settings in `.env` (all optional - defaults work fine):

```env
# Scanner configuration
SCANNER_MODEL_PATH=/path/to/pokemon_card_detector.onnx  # Auto-detected
SCANNER_CONF_THRESHOLD=0.5   # YOLO confidence threshold
SCANNER_MAX_HASH_DISTANCE=20 # Max Hamming distance for hash matching
```

### 6. Start the Server

```bash
cd backend
uvicorn app.main:app --reload
```

You should see:
```
🔍 Initializing card scanner...
✅ Card scanner ready (detector: True, matcher: True, hashes: 3326)
```

## API Endpoints

### Scanner Status

```http
GET /api/scanner/status
```

Response:
```json
{
  "ready": true,
  "detector_loaded": true,
  "matcher_loaded": true,
  "hash_count": 3326,
  "message": "Scanner ready"
}
```

### Scan Image (File Upload)

```http
POST /api/scanner/scan
Content-Type: multipart/form-data

file: <image file>
detect_only: false
```

### Scan Image (Base64)

```http
POST /api/scanner/scan/base64
Content-Type: application/json

{
  "image": "data:image/jpeg;base64,...",
  "detect_only": false
}
```

Response:
```json
{
  "success": true,
  "result": {
    "detections": [
      {"bbox": [100, 50, 400, 550], "confidence": 0.95}
    ],
    "matches": [
      {
        "card_id": 482,
        "sku": "sv10-001",
        "name": "Sprigatito (001)",
        "set_name": "SV10: Destined Rivals",
        "confidence": 0.92,
        "hash_distance": 8,
        "quantity": 5,
        "price": 0.25
      }
    ],
    "processing_time_ms": 150
  }
}
```

### Quick Add to Inventory

```http
POST /api/scanner/quick-add
Content-Type: application/json

{
  "image": "data:image/jpeg;base64,...",
  "warehouse_id": 1,
  "quantity": 1,
  "confirm_match": true
}
```

### WebSocket Streaming

```javascript
const ws = new WebSocket('ws://localhost:8000/api/scanner/stream');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'scan',
    image: 'data:image/jpeg;base64,...'
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'result') {
    console.log(data.result);
  }
};
```

## Frontend Usage

The scanner is integrated into the Scanner page with two modes:

1. **Search Mode**: Manual text search (existing functionality)
2. **Camera Mode**: ML-powered camera scanning

### Camera Mode Features

- Live webcam preview with detection overlays
- Manual "Scan Now" button
- Auto-scan mode (scans every 1.5 seconds)
- Image upload support
- Match results show SKU, stock, price, confidence
- One-click add to queue (uses Odoo product ID directly)

## How It Works

### Hash Matching

1. Scanner loads all `x_phash` values from Odoo products into memory cache
2. When you scan an image, it computes the pHash of the cropped card
3. Compares against all cached hashes using Hamming distance
4. Returns closest matches (distance ≤ 20 bits = ~92% similarity)

### Why x_phash on Odoo?

- **No duplicate data** - card info lives in one place
- **Real-time inventory** - matches include current stock/price
- **Easy maintenance** - new products get hashes via import scripts
- **Leverages existing infrastructure** - no new databases

## Training Tips

### Dataset Preparation

1. Take 50-100 photos of cards with varied:
   - Lighting (bright, dim, shadows)
   - Angles (straight, tilted)
   - Backgrounds (desk, mat, hand-held)
   - Distances (close, medium, far)

2. Include edge cases:
   - Multiple cards in frame
   - Partially visible cards
   - Cards in sleeves/toploaders
   - Graded slabs (if applicable)

3. Use Roboflow augmentation:
   - Blur (simulates camera focus)
   - Noise (simulates webcam quality)
   - Brightness variation

### Improving Accuracy

**Detection (YOLO)**:
- More training data improves detection
- Use `yolov8s.pt` instead of nano for better accuracy (slower)
- Lower `conf_threshold` for more detections

**Identification (Hash)**:
- Increase `max_hash_distance` for more lenient matching
- Ensure product images in Odoo are high quality
- The hash is computed from product images, not card photos

## Troubleshooting

### "Scanner not initialized"

Check that:
1. ONNX model exists at the expected path
2. Odoo connection is working
3. Products have `x_phash` populated

```bash
# Check model file
ls backend/app/models/scanner/

# Check Odoo products with hashes
PGPASSWORD=odoo psql -h HOST -U odoo -d "TCG-Cards" -c \
  "SELECT COUNT(*) FROM product_template WHERE x_phash IS NOT NULL;"
```

### "No hashes loaded from Odoo"

The scanner couldn't load product hashes:
1. Verify Odoo connection settings in `.env`
2. Check if `x_phash` field exists on `product.template`
3. Run `populate_phash.py` if products are missing hashes

### Low Detection Accuracy

1. Retrain YOLO with more data
2. Ensure training images match real-world conditions
3. Try smaller `conf_threshold`

### Low Identification Accuracy

1. Increase `max_hash_distance` (try 25-30)
2. Ensure Odoo product images are clear and high-quality
3. Check that cards are well-lit and in focus when scanning

### Camera Not Working

1. Check browser permissions
2. Try HTTPS (required for camera on some browsers)
3. Use Chrome or Firefox (better camera support)

## Performance

### Typical Performance (i5 CPU)

| Operation | Time |
|-----------|------|
| YOLO Detection | ~50-100ms |
| Hash Matching | ~10-20ms |
| **Total** | ~60-120ms |

### Memory Usage

The hash cache loads all product hashes into memory:
- ~3,300 products ≈ 2-3 MB RAM
- Scales linearly with product count

## Adding New Products

When you import new sets, hashes are populated automatically if your import script computes them. Otherwise:

```bash
# Populate hashes for new products
python scripts/populate_phash.py

# Or for specific set
python scripts/populate_phash.py --set "NEW_SET_NAME"
```

Then restart the backend to reload the hash cache, or call the refresh endpoint.
