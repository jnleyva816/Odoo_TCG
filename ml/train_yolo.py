#!/usr/bin/env python3
"""
YOLOv8 Training Script for Pokemon Card Detection

This script trains a YOLOv8 model to detect Pokemon cards in images.
Designed to run on:
- Local machine with GPU (CUDA)
- Kaggle Notebooks (free T4 GPU)
- Google Colab

The trained model detects a single class: 'pokemon-card'
After training, export to ONNX for efficient CPU inference on the server.

Usage:
    # Train locally
    python train_yolo.py --data ./data/roboflow/data.yaml --epochs 100
    
    # Train on Kaggle (copy this script to a notebook cell)
    # !pip install ultralytics
    # from train_yolo import train_model
    # train_model(data_yaml="/kaggle/working/dataset/data.yaml")
"""

import argparse
import logging
from pathlib import Path
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def train_model(
    data_yaml: str = "./data/roboflow/data.yaml",
    model_size: str = "n",  # n=nano, s=small, m=medium, l=large, x=xlarge
    epochs: int = 100,
    imgsz: int = 640,
    batch: int = 16,
    device: Optional[str] = None,  # None = auto-detect, "0" = GPU 0, "cpu" = CPU
    project: str = "runs/detect",
    name: str = "pokemon_card_detector",
    resume: bool = False,
    patience: int = 50,  # Early stopping patience
) -> Path:
    """
    Train YOLOv8 model for Pokemon card detection.
    
    Args:
        data_yaml: Path to data.yaml file from Roboflow export
        model_size: YOLO model size (n/s/m/l/x) - 'n' recommended for CPU inference
        epochs: Number of training epochs
        imgsz: Input image size (640 is standard)
        batch: Batch size (reduce if OOM errors)
        device: Device to train on (None=auto, "0"=GPU, "cpu"=CPU)
        project: Directory to save training runs
        name: Name for this training run
        resume: Resume from last checkpoint
        patience: Early stopping patience (epochs without improvement)
    
    Returns:
        Path to the best trained weights file
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed. Run: pip install ultralytics")
        raise
    
    # Validate data.yaml exists
    data_path = Path(data_yaml)
    if not data_path.exists():
        raise FileNotFoundError(f"Data YAML not found: {data_yaml}")
    
    logger.info("=" * 60)
    logger.info("Pokemon Card Detector - YOLOv8 Training")
    logger.info("=" * 60)
    logger.info(f"Data YAML: {data_yaml}")
    logger.info(f"Model size: yolov8{model_size}")
    logger.info(f"Epochs: {epochs}")
    logger.info(f"Image size: {imgsz}")
    logger.info(f"Batch size: {batch}")
    logger.info(f"Device: {device or 'auto'}")
    logger.info("=" * 60)
    
    # Load pretrained model (transfer learning from COCO weights)
    model_name = f"yolov8{model_size}.pt"
    logger.info(f"Loading pretrained model: {model_name}")
    model = YOLO(model_name)
    
    # Train the model
    logger.info("Starting training...")
    results = model.train(
        data=str(data_path),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        project=project,
        name=name,
        resume=resume,
        patience=patience,
        # Augmentation settings optimized for card detection
        hsv_h=0.015,  # Slight hue variation
        hsv_s=0.4,    # Saturation variation
        hsv_v=0.4,    # Value/brightness variation
        degrees=15.0,  # Slight rotation (cards held at angles)
        translate=0.1, # Translation
        scale=0.3,     # Scale variation
        shear=5.0,     # Shear
        perspective=0.0005,  # Perspective transform
        flipud=0.0,    # No vertical flip (cards have orientation)
        fliplr=0.0,    # No horizontal flip
        mosaic=0.5,    # Mosaic augmentation (good for detection)
        mixup=0.0,     # Disable mixup for single-class
        # Training settings
        amp=True,      # Automatic mixed precision
        workers=8,     # Data loader workers
        cache=True,    # Cache images for faster training
        plots=True,    # Generate training plots
        save=True,     # Save checkpoints
        save_period=10, # Save every 10 epochs
    )
    
    # Find best weights
    best_weights = Path(project) / name / "weights" / "best.pt"
    if not best_weights.exists():
        # Try with numbered run directory
        run_dirs = sorted(Path(project).glob(f"{name}*"))
        if run_dirs:
            best_weights = run_dirs[-1] / "weights" / "best.pt"
    
    logger.info("=" * 60)
    logger.info("Training Complete!")
    logger.info(f"Best weights saved to: {best_weights}")
    logger.info("=" * 60)
    
    return best_weights


def export_to_onnx(
    weights_path: str,
    output_dir: Optional[str] = None,
    imgsz: int = 640,
    simplify: bool = True,
    opset: int = 12,
    dynamic: bool = False,
) -> Path:
    """
    Export trained YOLO model to ONNX format for CPU inference.
    
    ONNX is critical for server deployment:
    - Much faster inference on CPU (no PyTorch overhead)
    - Smaller file size
    - Cross-platform compatibility
    
    Args:
        weights_path: Path to trained .pt weights file
        output_dir: Directory to save ONNX file (default: same as weights)
        imgsz: Input image size (must match training)
        simplify: Simplify ONNX graph (recommended)
        opset: ONNX opset version (12 is widely compatible)
        dynamic: Use dynamic input shapes (for variable batch sizes)
    
    Returns:
        Path to exported .onnx file
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed. Run: pip install ultralytics")
        raise
    
    weights = Path(weights_path)
    if not weights.exists():
        raise FileNotFoundError(f"Weights file not found: {weights_path}")
    
    logger.info("=" * 60)
    logger.info("Exporting to ONNX Format")
    logger.info("=" * 60)
    logger.info(f"Input weights: {weights_path}")
    logger.info(f"Image size: {imgsz}")
    logger.info(f"Simplify: {simplify}")
    logger.info(f"Opset: {opset}")
    logger.info("=" * 60)
    
    # Load model
    model = YOLO(str(weights))
    
    # Export to ONNX
    onnx_path = model.export(
        format="onnx",
        imgsz=imgsz,
        simplify=simplify,
        opset=opset,
        dynamic=dynamic,
    )
    
    onnx_file = Path(onnx_path)
    
    # Move to output directory if specified
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        new_path = output_path / onnx_file.name
        onnx_file.rename(new_path)
        onnx_file = new_path
    
    logger.info("=" * 60)
    logger.info("ONNX Export Complete!")
    logger.info(f"ONNX file: {onnx_file}")
    logger.info(f"File size: {onnx_file.stat().st_size / 1024 / 1024:.2f} MB")
    logger.info("=" * 60)
    logger.info("")
    logger.info("Next steps:")
    logger.info("1. Copy the .onnx file to your server: backend/app/models/scanner/")
    logger.info("2. Update SCANNER_MODEL_PATH in your .env file")
    logger.info("3. Restart the backend service")
    
    return onnx_file


def validate_model(
    weights_path: str,
    data_yaml: str = "./data/roboflow/data.yaml",
    imgsz: int = 640,
    device: Optional[str] = None,
) -> dict:
    """
    Validate trained model on test dataset.
    
    Args:
        weights_path: Path to trained weights
        data_yaml: Path to data.yaml
        imgsz: Image size
        device: Device for inference
    
    Returns:
        Validation metrics dictionary
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed. Run: pip install ultralytics")
        raise
    
    logger.info("Running validation...")
    model = YOLO(weights_path)
    
    results = model.val(
        data=data_yaml,
        imgsz=imgsz,
        device=device,
        plots=True,
    )
    
    metrics = {
        "mAP50": results.box.map50,
        "mAP50-95": results.box.map,
        "precision": results.box.mp,
        "recall": results.box.mr,
    }
    
    logger.info("=" * 60)
    logger.info("Validation Results")
    logger.info("=" * 60)
    for key, value in metrics.items():
        logger.info(f"{key}: {value:.4f}")
    logger.info("=" * 60)
    
    return metrics


def run_inference_test(
    weights_path: str,
    image_path: str,
    output_dir: str = "./runs/detect/test",
    conf_threshold: float = 0.5,
) -> None:
    """
    Run inference on a test image and save visualization.
    
    Args:
        weights_path: Path to trained weights (.pt or .onnx)
        image_path: Path to test image
        output_dir: Directory to save results
        conf_threshold: Confidence threshold for detections
    """
    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics not installed. Run: pip install ultralytics")
        raise
    
    logger.info(f"Running inference on: {image_path}")
    model = YOLO(weights_path)
    
    results = model.predict(
        source=image_path,
        conf=conf_threshold,
        save=True,
        project=output_dir,
        name="inference",
    )
    
    for r in results:
        boxes = r.boxes
        logger.info(f"Detected {len(boxes)} card(s)")
        for box in boxes:
            conf = box.conf[0].item()
            xyxy = box.xyxy[0].tolist()
            logger.info(f"  - Confidence: {conf:.2f}, Box: {xyxy}")


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Train YOLOv8 for Pokemon card detection"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train the model")
    train_parser.add_argument(
        "--data", default="./data/roboflow/data.yaml",
        help="Path to data.yaml"
    )
    train_parser.add_argument(
        "--model", default="n", choices=["n", "s", "m", "l", "x"],
        help="Model size (n=nano, s=small, etc.)"
    )
    train_parser.add_argument("--epochs", type=int, default=100)
    train_parser.add_argument("--imgsz", type=int, default=640)
    train_parser.add_argument("--batch", type=int, default=16)
    train_parser.add_argument("--device", default=None)
    train_parser.add_argument("--resume", action="store_true")
    
    # Export command
    export_parser = subparsers.add_parser("export", help="Export to ONNX")
    export_parser.add_argument("--weights", required=True, help="Path to .pt weights")
    export_parser.add_argument("--output", help="Output directory")
    export_parser.add_argument("--imgsz", type=int, default=640)
    
    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validate model")
    val_parser.add_argument("--weights", required=True, help="Path to weights")
    val_parser.add_argument("--data", default="./data/roboflow/data.yaml")
    
    # Test inference command
    test_parser = subparsers.add_parser("test", help="Test inference on image")
    test_parser.add_argument("--weights", required=True, help="Path to weights")
    test_parser.add_argument("--image", required=True, help="Path to test image")
    test_parser.add_argument("--conf", type=float, default=0.5)
    
    args = parser.parse_args()
    
    if args.command == "train":
        train_model(
            data_yaml=args.data,
            model_size=args.model,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            resume=args.resume,
        )
    elif args.command == "export":
        export_to_onnx(
            weights_path=args.weights,
            output_dir=args.output,
            imgsz=args.imgsz,
        )
    elif args.command == "validate":
        validate_model(
            weights_path=args.weights,
            data_yaml=args.data,
        )
    elif args.command == "test":
        run_inference_test(
            weights_path=args.weights,
            image_path=args.image,
            conf_threshold=args.conf,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
