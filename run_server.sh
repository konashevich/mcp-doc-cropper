#!/bin/bash
PROJECT_DIR="/mnt/merged_ssd/mcp-doc-cropper"
# Use the NPU virtual environment (Python 3.10 + rknnlite2)
VENV_PYTHON="/home/pi/npu_env/bin/python"

echo "Starting Document Cropper MCP Server (NPU Enabled)..."
cd $PROJECT_DIR
# Run as module to allow relative imports (from .npu_inference import ...)
# Run as module to allow relative imports
$VENV_PYTHON -m src.server
