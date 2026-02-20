#!/usr/bin/env python3
"""
Export MobileNetV3 as an embedding model (feature extractor) to ONNX.

This creates a model that converts images into 960-dimensional vectors
for similarity search. The classification head is removed, keeping only
the feature extraction layers.

Usage:
    python export_embedding_model.py

Output:
    backend/app/models/scanner/card_embedder.onnx
"""

import sys
from pathlib import Path

# Check dependencies
try:
    import torch
    from torchvision.models import MobileNet_V3_Large_Weights, mobilenet_v3_large
except ImportError:
    print("ERROR: PyTorch not installed. Run:")
    print("  pip install torch torchvision")
    sys.exit(1)

import torch.nn as nn


class CardEmbedder(nn.Module):
    """
    MobileNetV3-Large feature extractor for card embeddings.

    Removes the classification head, outputs a 960-dim vector.
    """

    def __init__(self):
        super().__init__()
        # Load pretrained MobileNetV3-Large
        weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
        base_model = mobilenet_v3_large(weights=weights)

        # Keep everything except the classifier
        self.features = base_model.features
        self.avgpool = base_model.avgpool

        # The output of avgpool is (batch, 960, 1, 1)
        # We'll flatten it to (batch, 960)

    def forward(self, x):
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)
        # L2 normalize for cosine similarity
        x = nn.functional.normalize(x, p=2, dim=1)
        return x


def main():
    output_dir = Path(__file__).parent.parent / "backend" / "app" / "models" / "scanner"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "card_embedder.onnx"

    print("=" * 60)
    print("Card Embedding Model Exporter")
    print("=" * 60)

    # Create model
    print("\n1. Loading MobileNetV3-Large pretrained weights...")
    model = CardEmbedder()
    model.eval()

    # Test the model
    print("2. Testing model output shape...")
    dummy_input = torch.randn(1, 3, 224, 224)
    with torch.no_grad():
        output = model(dummy_input)
    print(f"   Input shape: {dummy_input.shape}")
    print(f"   Output shape: {output.shape}")  # Should be (1, 960)
    print(f"   Output norm: {torch.norm(output).item():.4f}")  # Should be ~1.0 (normalized)

    # Export to ONNX
    print(f"\n3. Exporting to ONNX: {output_path}")
    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["embedding"],
        dynamic_axes={
            "input": {0: "batch_size"},
            "embedding": {0: "batch_size"},
        },
    )

    # Verify the exported model
    print("\n4. Verifying ONNX model...")
    try:
        import numpy as np
        import onnxruntime as ort

        session = ort.InferenceSession(str(output_path))

        # Get input/output info
        input_info = session.get_inputs()[0]
        output_info = session.get_outputs()[0]
        print(f"   Input: {input_info.name}, shape={input_info.shape}")
        print(f"   Output: {output_info.name}, shape={output_info.shape}")

        # Run inference
        test_input = np.random.randn(1, 3, 224, 224).astype(np.float32)
        result = session.run(None, {input_info.name: test_input})
        print(f"   Test inference: output shape={result[0].shape}")

    except ImportError:
        print("   (onnxruntime not installed, skipping verification)")

    print("\n" + "=" * 60)
    print("SUCCESS!")
    print("=" * 60)
    print(f"Model saved to: {output_path}")
    print(f"Model size: {output_path.stat().st_size / 1024 / 1024:.1f} MB")
    print("\nNext steps:")
    print("1. Run: python scripts/build_card_index.py")
    print("   This will create embeddings for all cards in Odoo")


if __name__ == "__main__":
    main()
