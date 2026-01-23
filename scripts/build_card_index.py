#!/usr/bin/env python3
"""
Build FAISS vector index from all card images in Odoo.

This script:
1. Loads the card_embedder.onnx model
2. Fetches all product images from Odoo
3. Computes embeddings for each image (with augmentations for robustness)
4. Builds a FAISS index for fast similarity search
5. Saves the index and metadata

Usage:
    # Build full index with augmentations (recommended)
    python build_card_index.py

    # Build without augmentations (faster, less accurate)
    python build_card_index.py --no-augment

    # Dry run (test with 10 cards)
    python build_card_index.py --dry-run

    # Filter by set
    python build_card_index.py --set "SV10"

Output:
    backend/app/models/scanner/card_index.faiss
    backend/app/models/scanner/card_metadata.json
"""

import argparse
import base64
import io
import json
import logging
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageOps

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

# Check dependencies
try:
    import onnxruntime as ort
except ImportError:
    print("ERROR: onnxruntime not installed. Run: pip install onnxruntime")
    sys.exit(1)

try:
    import faiss
except ImportError:
    print("ERROR: faiss not installed. Run: pip install faiss-cpu")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Paths
MODEL_DIR = Path(__file__).parent.parent / "backend" / "app" / "models" / "scanner"
EMBEDDER_PATH = MODEL_DIR / "card_embedder.onnx"
INDEX_PATH = MODEL_DIR / "card_index.faiss"
METADATA_PATH = MODEL_DIR / "card_metadata.json"

# Image preprocessing constants (MobileNetV3 expects ImageNet normalization)
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
INPUT_SIZE = 224


def augment_image(image: Image.Image) -> list[Image.Image]:
    """
    Generate augmented versions of an image for robust matching.

    Returns a list of images including:
    - Original
    - Brightness variations (+20%, -20%)
    - Contrast variations (+20%, -20%)
    - Warmer color temperature
    - Cooler color temperature

    This helps match camera-captured images with varying lighting conditions.
    """
    augmented = [image]  # Always include original

    # Brightness variations (simulate different lighting)
    brightness = ImageEnhance.Brightness(image)
    augmented.append(brightness.enhance(1.2))  # 20% brighter
    augmented.append(brightness.enhance(0.8))  # 20% darker

    # Contrast variations (simulate different camera settings)
    contrast = ImageEnhance.Contrast(image)
    augmented.append(contrast.enhance(1.2))  # 20% more contrast
    augmented.append(contrast.enhance(0.8))  # 20% less contrast

    # Color temperature variations (simulate warm/cool lighting)
    # Warmer (more yellow/red)
    warmer = image.copy()
    r, g, b = warmer.split()
    r = r.point(lambda x: min(255, int(x * 1.1)))
    b = b.point(lambda x: int(x * 0.9))
    augmented.append(Image.merge('RGB', (r, g, b)))

    # Cooler (more blue)
    cooler = image.copy()
    r, g, b = cooler.split()
    r = r.point(lambda x: int(x * 0.9))
    b = b.point(lambda x: min(255, int(x * 1.1)))
    augmented.append(Image.merge('RGB', (r, g, b)))

    return augmented


def preprocess_for_embedding(image: Image.Image) -> Image.Image:
    """
    Preprocess image before computing embedding.

    - Convert to RGB
    - Auto-contrast to normalize lighting
    - Resize to standard card dimensions first (preserves aspect ratio info)
    """
    if image.mode != "RGB":
        image = image.convert("RGB")

    # Auto-contrast to normalize brightness/contrast
    try:
        image = ImageOps.autocontrast(image, cutoff=2)
    except Exception:
        pass

    return image


def get_odoo_client():
    """Get Odoo XML-RPC client."""
    import xmlrpc.client

    url = os.getenv("ODOO_URL", "http://localhost:8069")
    db = os.getenv("ODOO_DB", "odoo")
    user = os.getenv("ODOO_USER", "")
    password = os.getenv("ODOO_PASSWORD", "")

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, password, {})

    if not uid:
        raise Exception("Odoo authentication failed")

    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
    return models, db, uid, password


def preprocess_image(image_data: bytes) -> np.ndarray:
    """
    Preprocess image for MobileNetV3.

    - Resize to 224x224
    - Convert to RGB
    - Normalize with ImageNet mean/std
    - Convert to NCHW format
    """
    image = Image.open(io.BytesIO(image_data))

    if image.mode != "RGB":
        image = image.convert("RGB")

    # Resize to 224x224 (MobileNet input size)
    image = image.resize((INPUT_SIZE, INPUT_SIZE), Image.Resampling.LANCZOS)

    # Convert to numpy array (HWC, 0-255)
    img_array = np.array(image, dtype=np.float32) / 255.0

    # Normalize with ImageNet stats
    img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD

    # Convert to NCHW format (batch, channels, height, width)
    img_array = img_array.transpose(2, 0, 1)
    img_array = np.expand_dims(img_array, axis=0)

    return img_array


class EmbeddingModel:
    """ONNX-based embedding model."""

    def __init__(self, model_path: Path):
        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.session = ort.InferenceSession(str(model_path))
        self.input_name = self.session.get_inputs()[0].name
        self.output_name = self.session.get_outputs()[0].name

        logger.info(f"Loaded embedding model: {model_path}")

    def embed(self, image_data: bytes) -> np.ndarray:
        """Compute embedding for an image."""
        input_array = preprocess_image(image_data)
        result = self.session.run([self.output_name], {self.input_name: input_array})
        return result[0][0]  # Return 1D array (960,)

    def embed_batch(self, images: list[bytes], batch_size: int = 32) -> np.ndarray:
        """Compute embeddings for multiple images."""
        all_embeddings = []

        for i in range(0, len(images), batch_size):
            batch = images[i:i + batch_size]
            inputs = np.vstack([preprocess_image(img) for img in batch])
            result = self.session.run([self.output_name], {self.input_name: inputs})
            all_embeddings.append(result[0])

        return np.vstack(all_embeddings)


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index for card images")
    parser.add_argument("--dry-run", action="store_true", help="Only process 10 cards")
    parser.add_argument("--set", help="Only process cards from this set/category")
    parser.add_argument("--batch-size", type=int, default=32, help="Batch size for embedding")
    parser.add_argument("--no-augment", action="store_true", help="Disable data augmentation (faster but less accurate)")
    args = parser.parse_args()

    use_augmentation = not args.no_augment

    print("=" * 60)
    print("Card Vector Index Builder (SOTA)")
    print("=" * 60)
    if use_augmentation:
        print("  Mode: WITH augmentation (7 variants per card)")
    else:
        print("  Mode: NO augmentation (1 embedding per card)")

    # Check model exists
    if not EMBEDDER_PATH.exists():
        print(f"\nERROR: Embedding model not found at {EMBEDDER_PATH}")
        print("Run first: python scripts/export_embedding_model.py")
        sys.exit(1)

    # Load embedding model
    print("\n1. Loading embedding model...")
    embedder = EmbeddingModel(EMBEDDER_PATH)

    # Connect to Odoo
    print("2. Connecting to Odoo...")
    models, db, uid, password = get_odoo_client()
    logger.info("Connected to Odoo")

    # Build domain
    domain = [("image_1920", "!=", False)]

    if args.set:
        cat_ids = models.execute_kw(
            db, uid, password,
            "product.category", "search",
            [[("name", "ilike", args.set)]],
        )
        if cat_ids:
            domain.append(("categ_id", "in", cat_ids))
            logger.info(f"Filtering to category: {args.set}")

    # Get product count
    product_count = models.execute_kw(
        db, uid, password,
        "product.product", "search_count",
        [domain],
    )

    limit = 10 if args.dry_run else None
    if args.dry_run:
        print(f"\n   [DRY RUN] Processing only 10 of {product_count} products")
    else:
        print(f"\n   Found {product_count} products with images")

    # Fetch products
    print("\n3. Fetching products from Odoo...")
    product_ids = models.execute_kw(
        db, uid, password,
        "product.product", "search",
        [domain],
        {"limit": limit} if limit else {},
    )

    # Process products and build embeddings
    augment_count = 7 if use_augmentation else 1
    print(f"\n4. Computing embeddings for {len(product_ids)} products...")
    if use_augmentation:
        print(f"   (Generating {augment_count} augmented variants per card)")

    embeddings = []
    metadata = []
    metadata_indices = []  # Maps embedding index -> metadata index
    errors = 0

    for i, pid in enumerate(product_ids):
        # Fetch product with image
        products = models.execute_kw(
            db, uid, password,
            "product.product", "read",
            [pid],
            {"fields": ["id", "name", "default_code", "categ_id", "image_1920", "qty_available", "list_price"]},
        )

        if not products:
            continue

        product = products[0]
        image_b64 = product.get("image_1920")

        if not image_b64:
            errors += 1
            continue

        try:
            # Decode image
            image_data = base64.b64decode(image_b64)
            image = Image.open(io.BytesIO(image_data))

            # Preprocess
            image = preprocess_for_embedding(image)

            # Create metadata entry (one per card, not per augmentation)
            card_metadata = {
                "id": product["id"],
                "sku": product.get("default_code") or "",
                "name": product.get("name") or "",
                "set_name": product["categ_id"][1] if product.get("categ_id") else "",
                "quantity": int(product.get("qty_available") or 0),
                "price": float(product.get("list_price") or 0),
            }
            metadata_idx = len(metadata)
            metadata.append(card_metadata)

            # Generate augmented images and compute embeddings
            if use_augmentation:
                augmented_images = augment_image(image)
            else:
                augmented_images = [image]

            for aug_img in augmented_images:
                # Convert to bytes for embedding
                buf = io.BytesIO()
                aug_img.save(buf, format='PNG')
                aug_data = buf.getvalue()

                embedding = embedder.embed(aug_data)
                embeddings.append(embedding)
                metadata_indices.append(metadata_idx)

            if (i + 1) % 100 == 0:
                logger.info(f"   Processed {i + 1}/{len(product_ids)} products ({len(embeddings)} embeddings)")

        except Exception as e:
            logger.warning(f"   Error processing product {pid}: {e}")
            errors += 1

    if not embeddings:
        print("\nERROR: No embeddings computed!")
        sys.exit(1)

    # Stack embeddings into a matrix
    print(f"\n5. Building FAISS index ({len(embeddings)} vectors from {len(metadata)} cards)...")
    embeddings_matrix = np.vstack(embeddings).astype(np.float32)

    # Create FAISS index (Inner Product = Cosine Similarity for normalized vectors)
    dimension = embeddings_matrix.shape[1]  # 960
    index = faiss.IndexFlatIP(dimension)  # Inner Product (cosine for L2-normalized vectors)
    index.add(embeddings_matrix)

    print(f"   Index dimension: {dimension}")
    print(f"   Index size: {index.ntotal} vectors")
    print(f"   Unique cards: {len(metadata)}")

    # Save index and metadata
    print("\n6. Saving index and metadata...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    faiss.write_index(index, str(INDEX_PATH))
    logger.info(f"   Saved index: {INDEX_PATH}")

    # Save metadata with index mapping
    index_data = {
        "metadata": metadata,
        "index_to_metadata": metadata_indices,  # Maps FAISS index -> metadata index
    }
    with open(METADATA_PATH, "w") as f:
        json.dump(index_data, f)
    logger.info(f"   Saved metadata: {METADATA_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"   Cards indexed: {len(metadata)}")
    print(f"   Total embeddings: {len(embeddings)} ({augment_count}x augmentation)")
    print(f"   Errors: {errors}")
    print(f"   Index file: {INDEX_PATH} ({INDEX_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"   Metadata file: {METADATA_PATH}")
    print("\nNext: Restart the backend to use the new vector search!")


if __name__ == "__main__":
    main()
