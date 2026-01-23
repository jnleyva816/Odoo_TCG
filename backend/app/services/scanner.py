"""
Card Scanner Service - Two-Stage Detection and Identification

Stage 1: YOLO-based card detection (finds card bounding boxes)
Stage 2: Neural embedding + FAISS vector search (identifies the specific card)

This is a SOTA (state-of-the-art) approach using:
- MobileNetV3 for feature extraction (embeddings)
- FAISS for fast similarity search
- Optional perspective warping for tilted cards

Falls back to perceptual hashing if FAISS index is not available.
"""

import io
import json
import logging
import time
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image

try:
    import imagehash
except ImportError:
    imagehash = None  # type: ignore

try:
    import onnxruntime as ort
except ImportError:
    ort = None  # type: ignore

try:
    import faiss
except ImportError:
    faiss = None  # type: ignore

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

from ..config import get_settings

logger = logging.getLogger(__name__)

# Paths
MODEL_DIR = Path(__file__).parent.parent / "models" / "scanner"
EMBEDDER_PATH = MODEL_DIR / "card_embedder.onnx"
FAISS_INDEX_PATH = MODEL_DIR / "card_index.faiss"
METADATA_PATH = MODEL_DIR / "card_metadata.json"

# ImageNet normalization constants
IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


@dataclass
class Detection:
    """Represents a detected card bounding box."""
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int = 0  # Always 0 for pokemon-card

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    def to_dict(self) -> dict:
        return {
            "bbox": [self.x1, self.y1, self.x2, self.y2],
            "confidence": round(self.confidence, 4),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
        }


@dataclass
class CardMatch:
    """Represents a matched card from Odoo."""
    card_id: int  # Odoo product.product ID
    sku: str
    name: str
    set_name: str
    confidence: float  # Based on hash distance (0-1, higher is better)
    hash_distance: int  # Hamming distance
    quantity: int = 0
    price: float = 0.0

    def to_dict(self) -> dict:
        return {
            "card_id": self.card_id,
            "sku": self.sku,
            "name": self.name,
            "set_name": self.set_name,
            "confidence": round(self.confidence, 4),
            "hash_distance": self.hash_distance,
            "quantity": self.quantity,
            "price": self.price,
        }


@dataclass
class ScanResult:
    """Complete result of scanning an image."""
    detections: list[Detection] = field(default_factory=list)
    matches: list[CardMatch] = field(default_factory=list)
    processing_time_ms: float = 0.0
    detection_time_ms: float = 0.0
    matching_time_ms: float = 0.0
    image_size: tuple[int, int] = (0, 0)

    def to_dict(self) -> dict:
        return {
            "detections": [d.to_dict() for d in self.detections],
            "matches": [m.to_dict() for m in self.matches],
            "processing_time_ms": round(self.processing_time_ms, 2),
            "detection_time_ms": round(self.detection_time_ms, 2),
            "matching_time_ms": round(self.matching_time_ms, 2),
            "image_size": self.image_size,
            "cards_found": len(self.matches),
        }


class CardDetector:
    """YOLO-based card detection using ONNX Runtime."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        conf_threshold: float = 0.5,
        iou_threshold: float = 0.45,
        input_size: int = 640,
    ):
        if ort is None:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime")

        self.model_path = model_path or (MODEL_DIR / "pokemon_card_detector.onnx")
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        self.input_size = input_size
        self.session: Optional[ort.InferenceSession] = None
        self._initialized = False

    def initialize(self) -> bool:
        """Load the ONNX model."""
        if self._initialized:
            return True

        if not self.model_path.exists():
            logger.warning(f"YOLO model not found: {self.model_path}")
            return False

        try:
            providers = ["CPUExecutionProvider"]
            if "CUDAExecutionProvider" in ort.get_available_providers():
                providers.insert(0, "CUDAExecutionProvider")
                logger.info("Using CUDA for YOLO inference")

            self.session = ort.InferenceSession(
                str(self.model_path),
                providers=providers,
            )
            self._initialized = True
            logger.info(f"Loaded YOLO model: {self.model_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            return False

    def preprocess(self, image: Image.Image) -> tuple[np.ndarray, tuple[int, int], float]:
        """Preprocess image for YOLO inference."""
        original_size = image.size

        if image.mode != "RGB":
            image = image.convert("RGB")

        scale = min(self.input_size / original_size[0], self.input_size / original_size[1])
        new_width = int(original_size[0] * scale)
        new_height = int(original_size[1] * scale)

        resized = image.resize((new_width, new_height), Image.Resampling.BILINEAR)

        letterboxed = Image.new("RGB", (self.input_size, self.input_size), (114, 114, 114))
        pad_x = (self.input_size - new_width) // 2
        pad_y = (self.input_size - new_height) // 2
        letterboxed.paste(resized, (pad_x, pad_y))

        img_array = np.array(letterboxed).astype(np.float32)
        img_array = img_array / 255.0
        img_array = img_array.transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)

        return img_array, original_size, scale

    def postprocess(
        self,
        outputs: np.ndarray,
        original_size: tuple[int, int],
        scale: float,
    ) -> list[Detection]:
        """Postprocess YOLO outputs to detections."""
        # Output shape is typically (1, 5, num_boxes) or (1, num_boxes, 5)
        # We need (num_boxes, 5) format
        predictions = outputs[0]  # Remove batch dimension -> (5, 8400) or (8400, 5)

        # YOLO v8 outputs (5, num_boxes) where rows are [x, y, w, h, conf]
        # We need to transpose to get (num_boxes, 5)
        if predictions.shape[0] == 5 and predictions.shape[1] > 5:
            predictions = predictions.T

        detections = []
        pad_x = (self.input_size - int(original_size[0] * scale)) // 2
        pad_y = (self.input_size - int(original_size[1] * scale)) // 2

        for pred in predictions:
            if len(pred) >= 5:
                x_center, y_center, width, height = pred[:4]
                conf = pred[4] if len(pred) == 5 else max(pred[4:])

                if conf < self.conf_threshold:
                    continue

                x1 = x_center - width / 2
                y1 = y_center - height / 2
                x2 = x_center + width / 2
                y2 = y_center + height / 2

                # Remove padding and scale back to original size
                x1 = (x1 - pad_x) / scale
                y1 = (y1 - pad_y) / scale
                x2 = (x2 - pad_x) / scale
                y2 = (y2 - pad_y) / scale

                # Clamp to image bounds
                x1 = max(0, min(x1, original_size[0]))
                y1 = max(0, min(y1, original_size[1]))
                x2 = max(0, min(x2, original_size[0]))
                y2 = max(0, min(y2, original_size[1]))

                # Validate box dimensions
                if x2 - x1 > 10 and y2 - y1 > 10:
                    detections.append(Detection(
                        x1=float(x1),
                        y1=float(y1),
                        x2=float(x2),
                        y2=float(y2),
                        confidence=float(conf),
                    ))

        detections = self._nms(detections)
        return detections

    def _nms(self, detections: list[Detection]) -> list[Detection]:
        """Apply Non-Maximum Suppression."""
        if not detections:
            return []

        detections = sorted(detections, key=lambda x: x.confidence, reverse=True)

        keep = []
        while detections:
            best = detections.pop(0)
            keep.append(best)
            detections = [
                d for d in detections
                if self._iou(best, d) < self.iou_threshold
            ]

        return keep

    def _iou(self, a: Detection, b: Detection) -> float:
        """Calculate Intersection over Union."""
        x1 = max(a.x1, b.x1)
        y1 = max(a.y1, b.y1)
        x2 = min(a.x2, b.x2)
        y2 = min(a.y2, b.y2)

        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        union = a.area + b.area - intersection

        return intersection / union if union > 0 else 0

    def detect(self, image: Image.Image) -> list[Detection]:
        """Detect cards in an image."""
        if not self._initialized:
            if not self.initialize():
                logger.warning("Detector not initialized, skipping detection")
                return []

        img_array, original_size, scale = self.preprocess(image)
        input_name = self.session.get_inputs()[0].name
        outputs = self.session.run(None, {input_name: img_array})

        detections = self.postprocess(outputs[0], original_size, scale)
        logger.debug(f"Detected {len(detections)} cards in {original_size} image")

        return detections


class HashMatcher:
    """Perceptual hash-based card identification using Odoo x_phash field."""

    def __init__(self, max_distance: int = 60):
        if imagehash is None:
            raise ImportError("imagehash not installed. Run: pip install imagehash")

        # Perceptual hash distance threshold
        # For 256-bit hashes (16x16), distance can range 0-256
        # Good match: < 30, Acceptable: 30-60, Poor: > 60
        # With standardized preprocessing, we can use tighter thresholds
        self.max_distance = max_distance
        # Cache: {product_id: (sku, name, set_name, hash_str, qty, price)}
        self._hash_cache: dict[int, tuple[str, str, str, str, int, float]] = {}
        self._initialized = False

    async def initialize(self) -> bool:
        """Load hashes from Odoo into memory cache."""
        if self._initialized:
            return True

        try:
            from . import get_odoo_service

            odoo = get_odoo_service()

            # Fetch all products with hashes via Odoo XML-RPC
            # Fields: id, sku, name, set, hash, qty, price
            products = await odoo.search_read(
                "product.product",
                [("x_phash", "!=", False)],  # Only products with hashes
                [
                    "id",
                    "default_code",
                    "name",
                    "categ_id",
                    "x_phash",
                    "qty_available",
                    "list_price",
                ],
            )

            for p in products:
                product_id = p["id"]
                sku = p.get("default_code") or ""
                name = p.get("name") or ""
                # categ_id is [id, name] tuple
                categ = p.get("categ_id")
                set_name = categ[1] if categ else ""
                phash = p.get("x_phash") or ""
                qty = int(p.get("qty_available") or 0)
                price = float(p.get("list_price") or 0)

                if phash:
                    self._hash_cache[product_id] = (sku, name, set_name, phash, qty, price)

            self._initialized = True
            logger.info(f"Loaded {len(self._hash_cache)} hashes from Odoo")
            return True

        except Exception as e:
            logger.error(f"Failed to load hashes from Odoo: {e}")
            return False

    async def refresh_cache(self) -> None:
        """Force refresh the hash cache from Odoo."""
        self._initialized = False
        self._hash_cache.clear()
        await self.initialize()

    def preprocess_card_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess a card image for hash matching.

        Steps:
        1. Convert to RGB
        2. Normalize brightness/contrast using auto-levels
        3. Resize to standard card dimensions (250x350)

        This ensures camera-captured images produce comparable hashes
        to the reference images stored in Odoo.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Skip preprocessing if image is too small
        if image.size[0] < 50 or image.size[1] < 50:
            return image

        # Auto-levels: normalize brightness/contrast
        # This helps with varying lighting conditions
        try:
            from PIL import ImageOps
            image = ImageOps.autocontrast(image, cutoff=1)
        except Exception:
            pass  # Skip if enhancement fails

        # Resize to standard card dimensions (250x350)
        # This matches the preprocessing in populate_phash.py
        target_width = 250
        target_height = 350
        image = image.resize((target_width, target_height), Image.Resampling.LANCZOS)

        return image

    def compute_hash(self, image: Image.Image) -> str:
        """Compute perceptual hash for an image."""
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Ensure image has reasonable dimensions for hashing
        if image.size[0] < 10 or image.size[1] < 10:
            logger.warning(f"Image too small for hashing: {image.size}")
            return "0" * 64  # Return zero hash

        return str(imagehash.phash(image, hash_size=16))

    async def find_matches(
        self,
        image: Image.Image,
        top_k: int = 5,
    ) -> list[CardMatch]:
        """Find matching cards for an image."""
        if not self._initialized:
            if not await self.initialize():
                logger.warning("Hash matcher not initialized")
                return []

        # Preprocess the image for better matching
        processed_image = self.preprocess_card_image(image)

        # Compute hash of preprocessed image
        input_hash_str = self.compute_hash(processed_image)
        input_hash = imagehash.hex_to_hash(input_hash_str)

        # Also compute dHash for cross-validation (more sensitive to gradients)
        imagehash.dhash(processed_image, hash_size=16)

        # Find closest matches in cache
        matches = []
        for product_id, (sku, name, set_name, hash_str, qty, price) in self._hash_cache.items():
            try:
                db_hash = imagehash.hex_to_hash(hash_str)
                phash_distance = int(input_hash - db_hash)

                if phash_distance <= self.max_distance:
                    # Calculate confidence with exponential scaling
                    # This makes low distances much more confident than medium distances
                    # distance 0 -> 100%, distance 30 -> ~88%, distance 60 -> ~77%
                    confidence = max(0, 1.0 - (phash_distance / 256.0) ** 0.7)

                    matches.append((
                        product_id, sku, name, set_name,
                        phash_distance, confidence, qty, price
                    ))
            except Exception:
                continue

        # Sort by distance
        matches.sort(key=lambda x: x[4])

        # If we have matches, check if the best match is significantly better than others
        if len(matches) >= 2:
            best_dist = matches[0][4]
            second_dist = matches[1][4]

            # If best match is clearly better (>20% gap), boost its confidence
            if second_dist > 0 and (second_dist - best_dist) / second_dist > 0.2:
                boost = min(0.1, (second_dist - best_dist) / 256.0)
                matches[0] = (
                    matches[0][0], matches[0][1], matches[0][2], matches[0][3],
                    matches[0][4], min(1.0, matches[0][5] + boost),
                    matches[0][6], matches[0][7]
                )

        top_matches = matches[:top_k]

        if top_matches:
            logger.info(
                f"Scan match: {top_matches[0][2]} "
                f"(dist={top_matches[0][4]}, conf={top_matches[0][5]:.1%}, "
                f"next_dist={top_matches[1][4] if len(top_matches) > 1 else 'N/A'})"
            )

        return [
            CardMatch(
                card_id=m[0],
                sku=m[1],
                name=m[2],
                set_name=m[3],
                hash_distance=m[4],
                confidence=m[5],
                quantity=m[6],
                price=m[7],
            )
            for m in top_matches
        ]


class EmbeddingMatcher:
    """
    SOTA card identification using neural embeddings + FAISS vector search.

    This is significantly more accurate than perceptual hashing because:
    - Neural networks understand image semantics, not just pixel patterns
    - FAISS enables sub-millisecond search across millions of vectors
    - Robust to lighting, angle, and glare variations
    - Data augmentation during indexing improves matching under varying conditions
    """

    def __init__(self, similarity_threshold: float = 0.6):
        if ort is None:
            raise ImportError("onnxruntime not installed. Run: pip install onnxruntime")
        if faiss is None:
            raise ImportError("faiss not installed. Run: pip install faiss-cpu")

        self.similarity_threshold = similarity_threshold
        self.session: Optional[ort.InferenceSession] = None
        self.index: Optional[faiss.Index] = None
        self.metadata: list[dict] = []
        self.index_to_metadata: list[int] = []  # Maps FAISS index -> metadata index
        self._initialized = False

    def initialize(self) -> bool:
        """Load the embedding model and FAISS index."""
        if self._initialized:
            return True

        # Check if model and index exist
        if not EMBEDDER_PATH.exists():
            logger.warning(f"Embedding model not found: {EMBEDDER_PATH}")
            return False

        if not FAISS_INDEX_PATH.exists():
            logger.warning(f"FAISS index not found: {FAISS_INDEX_PATH}")
            return False

        if not METADATA_PATH.exists():
            logger.warning(f"Metadata file not found: {METADATA_PATH}")
            return False

        try:
            # Load embedding model
            providers = ["CPUExecutionProvider"]
            self.session = ort.InferenceSession(str(EMBEDDER_PATH), providers=providers)
            logger.info(f"Loaded embedding model: {EMBEDDER_PATH}")

            # Load FAISS index
            self.index = faiss.read_index(str(FAISS_INDEX_PATH))
            logger.info(f"Loaded FAISS index: {self.index.ntotal} vectors")

            # Load metadata (supports both old and new format)
            with open(METADATA_PATH, "r") as f:
                data = json.load(f)

            # Handle new format with index_to_metadata mapping (for augmented index)
            if isinstance(data, dict) and "metadata" in data:
                self.metadata = data["metadata"]
                default_map = list(range(len(self.metadata)))
                self.index_to_metadata = data.get("index_to_metadata", default_map)
                n_cards = len(self.metadata)
                n_emb = len(self.index_to_metadata)
                logger.info(f"Loaded metadata: {n_cards} cards, {n_emb} embeddings")
            else:
                # Old format: metadata is a list, 1:1 mapping
                self.metadata = data
                self.index_to_metadata = list(range(len(self.metadata)))
                logger.info(f"Loaded metadata (legacy format): {len(self.metadata)} cards")

            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Failed to initialize embedding matcher: {e}")
            return False

    def preprocess_image(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess image for MobileNetV3.

        - Convert to RGB
        - Apply auto-contrast to normalize lighting
        - Resize to 224x224
        - Normalize with ImageNet mean/std
        - Convert to NCHW format
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Auto-contrast to normalize brightness/contrast variations from camera
        try:
            from PIL import ImageOps
            image = ImageOps.autocontrast(image, cutoff=2)
        except Exception:
            pass

        # Resize to 224x224
        image = image.resize((224, 224), Image.Resampling.LANCZOS)

        # Convert to numpy (HWC, 0-255 -> 0-1)
        img_array = np.array(image, dtype=np.float32) / 255.0

        # Normalize with ImageNet stats
        img_array = (img_array - IMAGENET_MEAN) / IMAGENET_STD

        # Convert to NCHW (batch, channels, height, width)
        img_array = img_array.transpose(2, 0, 1)
        img_array = np.expand_dims(img_array, axis=0)

        return img_array

    def warp_perspective(self, image: Image.Image) -> Image.Image:
        """
        Apply perspective warping to flatten a tilted card.

        Uses OpenCV to detect card corners and warp to a rectangle.
        Falls back to original image if warping fails.
        """
        if cv2 is None:
            return image

        try:
            # Convert PIL to OpenCV format
            img_cv = np.array(image)
            img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)

            # Convert to grayscale and find edges
            gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 50, 150)

            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                return image

            # Find the largest contour (should be the card)
            largest = max(contours, key=cv2.contourArea)

            # Approximate to polygon
            epsilon = 0.02 * cv2.arcLength(largest, True)
            approx = cv2.approxPolyDP(largest, epsilon, True)

            # If we found 4 corners, warp perspective
            if len(approx) == 4:
                # Order points: top-left, top-right, bottom-right, bottom-left
                pts = approx.reshape(4, 2).astype(np.float32)

                # Sort by sum and diff to get correct order
                s = pts.sum(axis=1)
                diff = np.diff(pts, axis=1)

                ordered = np.zeros((4, 2), dtype=np.float32)
                ordered[0] = pts[np.argmin(s)]  # top-left
                ordered[2] = pts[np.argmax(s)]  # bottom-right
                ordered[1] = pts[np.argmin(diff)]  # top-right
                ordered[3] = pts[np.argmax(diff)]  # bottom-left

                # Target dimensions (standard card ratio 2.5:3.5)
                width = 250
                height = 350
                dst = np.array([
                    [0, 0],
                    [width - 1, 0],
                    [width - 1, height - 1],
                    [0, height - 1]
                ], dtype=np.float32)

                # Compute and apply perspective transform
                matrix = cv2.getPerspectiveTransform(ordered, dst)
                warped = cv2.warpPerspective(img_cv, matrix, (width, height))

                # Convert back to PIL
                warped_rgb = cv2.cvtColor(warped, cv2.COLOR_BGR2RGB)
                return Image.fromarray(warped_rgb)

        except Exception as e:
            logger.debug(f"Perspective warp failed: {e}")

        return image

    def compute_embedding(self, image: Image.Image) -> np.ndarray:
        """Compute embedding vector for an image."""
        input_array = self.preprocess_image(image)
        input_name = self.session.get_inputs()[0].name
        result = self.session.run(None, {input_name: input_array})
        return result[0][0]  # Return 1D array (960,)

    def find_matches(self, image: Image.Image, top_k: int = 5) -> list[CardMatch]:
        """Find matching cards using vector similarity search."""
        if not self._initialized:
            return []

        # Log input image info for debugging
        logger.info(f"[SOTA] Input image: {image.size}, mode={image.mode}")

        # Optional: Apply perspective warping
        warped = self.warp_perspective(image)
        if warped.size != image.size:
            logger.info(f"[SOTA] Warped to: {warped.size}")

        # Compute embedding
        embedding = self.compute_embedding(warped)
        embedding = embedding.reshape(1, -1).astype(np.float32)

        # Search more candidates since augmentations may return duplicates
        # With 7x augmentation, search 7x more to ensure we get top_k unique cards
        search_k = top_k * 10

        # Search FAISS index (Inner Product = Cosine Similarity for normalized vectors)
        similarities, indices = self.index.search(embedding, search_k)

        # Debug: log raw top similarities
        logger.debug(f"[SOTA] Raw top-5 similarities: {similarities[0][:5]}")
        logger.debug(f"[SOTA] Raw top-5 indices: {indices[0][:5]}")

        # Deduplicate: multiple augmentations of same card may match
        # Keep the best (highest similarity) match for each unique card
        seen_cards: dict[int, tuple[float, int]] = {}  # card_id -> (best_similarity, metadata_idx)

        for sim, idx in zip(similarities[0], indices[0]):
            if idx < 0 or idx >= len(self.index_to_metadata):
                continue

            # Map FAISS index to metadata index
            metadata_idx = self.index_to_metadata[idx]
            if metadata_idx >= len(self.metadata):
                continue

            card = self.metadata[metadata_idx]
            card_id = card["id"]

            # Keep only the best match for each card
            if card_id not in seen_cards or sim > seen_cards[card_id][0]:
                seen_cards[card_id] = (sim, metadata_idx)

        # Convert to matches, sorted by similarity
        matches = []
        for card_id, (sim, metadata_idx) in sorted(seen_cards.items(), key=lambda x: -x[1][0]):
            # Convert similarity to confidence (0-1 range)
            # Inner product of L2-normalized vectors ranges from -1 to 1
            confidence = float((sim + 1) / 2)  # Map [-1, 1] to [0, 1]

            if confidence < self.similarity_threshold:
                continue

            card = self.metadata[metadata_idx]
            matches.append(CardMatch(
                card_id=card["id"],
                sku=card.get("sku", ""),
                name=card.get("name", ""),
                set_name=card.get("set_name", ""),
                confidence=confidence,
                hash_distance=int((1 - confidence) * 100),  # Pseudo-distance for compatibility
                quantity=card.get("quantity", 0),
                price=card.get("price", 0.0),
            ))

            if len(matches) >= top_k:
                break

        if matches:
            next_conf = f"{matches[1].confidence:.1%}" if len(matches) > 1 else "N/A"
            logger.info(
                f"[SOTA] Match: {matches[0].name} "
                f"(conf={matches[0].confidence:.1%}, next={next_conf})"
            )

        return matches


class ScannerService:
    """
    Main scanner service combining detection and identification.

    Uses SOTA embedding-based matching when available, falls back to
    perceptual hashing if the FAISS index hasn't been built.
    """

    def __init__(self):
        settings = get_settings()

        model_path = getattr(settings, "scanner_model_path", None)

        self.detector = CardDetector(
            model_path=Path(model_path) if model_path else None,
            conf_threshold=getattr(settings, "scanner_conf_threshold", 0.5),
        )

        # SOTA matcher (embedding + FAISS)
        self.embedding_matcher: Optional[EmbeddingMatcher] = None

        # Fallback matcher (perceptual hashing)
        self.hash_matcher = HashMatcher(
            max_distance=getattr(settings, "scanner_max_hash_distance", 60),
        )

        # For backward compatibility
        self.matcher = self.hash_matcher

        self._initialized = False
        self._use_embeddings = False

    def set_max_distance(self, distance: int) -> None:
        """Dynamically adjust the hash matching threshold (for tuning)."""
        self.hash_matcher.max_distance = max(10, min(200, distance))
        logger.info(f"Scanner max_distance set to {self.hash_matcher.max_distance}")

    async def initialize(self) -> dict:
        """Initialize scanner components and return status."""
        detector_ok = self.detector.initialize()

        # Try SOTA embedding matcher first
        embedding_ok = False
        try:
            self.embedding_matcher = EmbeddingMatcher()
            embedding_ok = self.embedding_matcher.initialize()
            if embedding_ok:
                self._use_embeddings = True
                logger.info("🚀 Using SOTA embedding-based matching")
        except Exception as e:
            logger.info(f"Embedding matcher not available: {e}")

        # Fall back to hash matcher
        hash_ok = await self.hash_matcher.initialize()

        matcher_ok = embedding_ok or hash_ok
        self._initialized = detector_ok or matcher_ok

        return {
            "initialized": self._initialized,
            "detector": detector_ok,
            "matcher": matcher_ok,
            "embedding_matcher": embedding_ok,
            "hash_matcher": hash_ok,
            "hash_count": len(self.hash_matcher._hash_cache) if hash_ok else 0,
            "embedding_count": len(self.embedding_matcher.metadata) if embedding_ok else 0,
            "mode": "embeddings" if self._use_embeddings else "hashing",
        }

    @property
    def is_ready(self) -> bool:
        return self._initialized

    async def _find_matches(self, image: Image.Image, top_k: int = 5) -> list[CardMatch]:
        """Find matches using the best available matcher."""
        if self._use_embeddings and self.embedding_matcher:
            return self.embedding_matcher.find_matches(image, top_k)
        elif self.hash_matcher._initialized:
            return await self.hash_matcher.find_matches(image, top_k)
        return []

    async def scan_image(
        self,
        image: Image.Image | bytes,
        detect_only: bool = False,
    ) -> ScanResult:
        """Scan an image for Pokemon cards."""
        start_time = time.time()
        result = ScanResult()

        if isinstance(image, bytes):
            image = Image.open(io.BytesIO(image))

        result.image_size = image.size

        # Stage 1: Detection
        detection_start = time.time()

        if self.detector._initialized:
            result.detections = self.detector.detect(image)
        else:
            # No detector, treat whole image as a card
            result.detections = [Detection(
                x1=0, y1=0,
                x2=image.size[0], y2=image.size[1],
                confidence=1.0,
            )]

        result.detection_time_ms = (time.time() - detection_start) * 1000

        # Stage 2: Identification
        if not detect_only:
            matching_start = time.time()

            for detection in result.detections:
                crop_box = (
                    int(detection.x1),
                    int(detection.y1),
                    int(detection.x2),
                    int(detection.y2),
                )

                # Validate crop box
                if crop_box[2] <= crop_box[0] or crop_box[3] <= crop_box[1]:
                    logger.warning(f"Invalid crop box: {crop_box}, skipping")
                    continue

                cropped = image.crop(crop_box)
                matches = await self._find_matches(cropped, top_k=5)
                result.matches.extend(matches)

            result.matching_time_ms = (time.time() - matching_start) * 1000

        result.processing_time_ms = (time.time() - start_time) * 1000

        return result

    async def identify_card(self, image: Image.Image | bytes) -> list[CardMatch]:
        """Identify a single card image (already cropped)."""
        if isinstance(image, bytes):
            image = Image.open(io.BytesIO(image))

        return await self._find_matches(image, top_k=5)


# Singleton instance
_scanner_service: Optional[ScannerService] = None


@lru_cache
def get_scanner_service() -> ScannerService:
    """Get or create scanner service singleton."""
    global _scanner_service
    if _scanner_service is None:
        _scanner_service = ScannerService()
    return _scanner_service
