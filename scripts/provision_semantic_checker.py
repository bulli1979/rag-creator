#!/usr/bin/env python3
"""Explicitly download pinned public weights, never corpus or chat content."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "documentApi"))
from app.config import get_base_directory
from app.semantic_support import MODEL, REVISION
from huggingface_hub import snapshot_download

if __name__ == "__main__":
    print(snapshot_download(MODEL, revision=REVISION,
          cache_dir=str(get_base_directory() / "model_cache"),
          allow_patterns=["*.json", "*.model", "model.safetensors"]))
    print(snapshot_download("mixedbread-ai/mxbai-embed-large-v1",
          revision="b33106f585b9ce46904ad7443a3b52b7a63e231c",
          cache_dir=str(get_base_directory()/"model_cache"),
          allow_patterns=["*.json","*.txt","model.safetensors","1_Pooling/*"],
          ignore_patterns=["onnx/*","openvino/*"]))
