#!/bin/bash
PROJECT_DIR="/mnt/merged_ssd/mcp-doc-cropper"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
UVICORN="$PROJECT_DIR/.venv/bin/uvicorn"

echo "Starting Document Cropper MCP Server..." # Run the server script (which runs both MCP and CropAPI)
cd $PROJECT_DIR
exec $VENV_PYTHON src/server.py
