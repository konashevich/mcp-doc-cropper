import base64
import sys
import socket
import numpy as np
import cv2
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import Response
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from .npu_inference import NPUInference

# --- Configuration ---
MODEL_PATH = "/mnt/merged_ssd/mcp-doc-cropper/yolo11n-seg.rknn"
PORT = 3099

# --- Global State ---
_model = None

# --- Helper Functions ---
def get_local_ip():
    """Detects the local LAN IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # duplicated request to a public DNS server to find our IP routing
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

SERVER_IP = "cropper-mcp.local"

def get_model():
    """Robust, lazy loading of the NPU model."""
    global _model
    if _model is not None:
        return _model
    
    print(f"Loading NPU model from {MODEL_PATH}...", file=sys.stderr)
    try:
        _model = NPUInference(MODEL_PATH)
        print("NPU Model loaded successfully.", file=sys.stderr)
        return _model
    except Exception as e:
        print(f"CRITICAL ERROR loading NPU model: {e}", file=sys.stderr)
        return None

import logging
# Pre-configure logging to avoid FastMCP's basicConfig call failing or being needed
logging.basicConfig(level=logging.INFO)

# --- MCP Server Definition ---
# Disable DNS rebinding protection to allow LAN access (e.g. from doc-cropper-lan)
mcp = FastMCP(
    "doc-cropper",
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)


@mcp.tool()
def get_crop_command(input_path: str, output_path: str = None) -> str:
    """
    Generates the terminal command to crop a local document image.
    Use this to process files efficiently without memory overhead.
    
    Args:
        input_path: Absolute path to the source image file.
        output_path: Optional absolute path for the result. 
                     If not provided, defaults to <original_name>_cropped.<ext>.
                     If same as input, handles safe overwrite.
    
    Returns:
        The exact 'curl' command to execute in the terminal.
    """
    import os
    from pathlib import Path
    
    # 1. Resolve Paths
    in_file = Path(input_path).resolve()
    
    if output_path:
        out_file = Path(output_path).resolve()
    else:
        # Default naming: name_cropped.ext
        out_file = in_file.with_name(f"{in_file.stem}_cropped{in_file.suffix}")

    # 2. Construct Server URL (Pointing to the Crop API Port)
    url = f"http://{SERVER_IP}:3098/crop"


    # 3. Handle Overwrite Safety
    # If input and output are the same file, we must write to temp first
    if in_file == out_file:
        temp_out = out_file.with_name(f"tmp_{out_file.name}")
        # Command: crop to temp -> move to original
        # Note: We use 'mv -f' to force overwrite
        cmd = f"curl -s -F 'file=@{in_file}' '{url}' -o '{temp_out}' && mv -f '{temp_out}' '{out_file}'"
    else:
        # Standard case
        cmd = f"curl -s -F 'file=@{in_file}' '{url}' -o '{out_file}'"

    return cmd

@mcp.tool()
def get_batch_crop_command(directory_path: str, extensions: list[str] = ["jpg", "jpeg", "png"], output_directory: str = None) -> str:
    """
    Generates a terminal command to crop ALL images in a directory sequentially.
    Use this for bulk processing. It prevents server crashes (OOM) by ensuring one-at-a-time processing.
    
    Args:
        directory_path: Absolute path to the folder containing images.
        extensions: List of file extensions to process (default: jpg, jpeg, png).
        output_directory: Optional. If set, saves cropped files here. 
                          If None, saves in-place with '_cropped' suffix.
    
    Returns:
        A bash loop command string ready to execute.
    """
    from pathlib import Path
    
    dir_path = Path(directory_path).resolve()
    # Construct Server URL
    url = f"http://{SERVER_IP}:3098/crop"
    
    # Build extension glob pattern
    # We use a simple loop over extensions to be shell-agnostic (bash/zsh) safe
    # "for ext in jpg png; do for file in dir/*.$ext; do ... done; done"
    
    ext_str = " ".join(extensions)
    
    # Script Logic:
    # 1. Loop through extensions
    # 2. Loop through files
    # 3. Construct Output Path
    # 4. Execute Curl
    
    # We construct a robust one-liner.
    # Note: We use python to safely construct the string, but the result is a shell command.
    
    cmd = f"""
    echo "Starting Batch Crop on {dir_path}..."
    for ext in {ext_str}; do
        for file in "{dir_path}"/*.$ext; do
            [ -e "$file" ] || continue
            echo "Processing $file..."
            
            # Define Output
            if [ -z "{output_directory or ''}" ]; then
                # In-place default: name_cropped.ext
                filename=$(basename "$file")
                stem="${{filename%.*}}"
                out_path="{dir_path}/${{stem}}_cropped.$ext"
            else
                # Custom output dir
                filename=$(basename "$file")
                mkdir -p "{output_directory}"
                out_path="{output_directory}/$filename"
            fi
            
            # Run Curl
            curl -s -F "file=@$file" "{url}" -o "$out_path"
        done
    done
    echo "Batch processing complete."
    """
    
    # Flatten whitespace for cleanliness (optional, but good for Agent readability)
    return " ".join(cmd.split())


# --- Core Logic ---
def run_crop(img: np.ndarray, model) -> np.ndarray:
    """Core cropping logic using NPU backend."""
    # Run inference
    # Returns list of dicts: [{'box': [x1,y1,x2,y2], 'score': float, 'class_id': int}, ...]
    results = model.run(img)
    
    if not results:
        print("No objects detected. Returning original.", file=sys.stderr)
        return img

    # Find largest box
    # Box format is [x1, y1, x2, y2]
    largest_result = max(results, key=lambda x: (x['box'][2] - x['box'][0]) * (x['box'][3] - x['box'][1]))
    x1, y1, x2, y2 = map(int, largest_result['box'])
    
    # Padding
    h, w = img.shape[:2]
    padding = 10
    x1 = max(0, x1 - padding)
    y1 = max(0, y1 - padding)
    x2 = min(w, x2 + padding)
    y2 = min(h, y2 + padding)

    return img[y1:y2, x1:x2]

# --- FastAPI App ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Attempt early load, but don't fail app if it fails (retry on request)
    get_model()
    yield
    # Shutdown
    global _model
    if _model:
        _model.release()
    _model = None

# --- HTTP Server (FastAPI) for Binary Transfer ---
crop_api_app = FastAPI(lifespan=lifespan)

@crop_api_app.post("/crop")
async def http_crop_endpoint(file: UploadFile = File(...)):
    """
    Direct HTTP endpoint for cropping images. Returns raw image bytes.
    Accepts: multipart/form-data file upload.
    Returns: image/jpeg
    """
    model = get_model()
    if model is None:
        raise HTTPException(status_code=503, detail="Model not loaded or invalid")
    
    try:
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image data")
            
        cropped_img = run_crop(img, model)
        
        _, buffer = cv2.imencode('.jpg', cropped_img)
        return Response(content=buffer.tobytes(), media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Server Execution ---
async def run_dual_servers():
    import uvicorn
    
    # 1. Configure MCP Server on Port 3099
    # We use mcp.sse_app directly as it works with Uvicorn
    config_mcp = uvicorn.Config(app=mcp.sse_app, host="0.0.0.0", port=3099, log_config=None)
    server_mcp = uvicorn.Server(config_mcp)

    # 2. Configure Crop API Server on Port 3098
    config_crop = uvicorn.Config(app=crop_api_app, host="0.0.0.0", port=3098, log_config=None)
    server_crop = uvicorn.Server(config_crop)

    print("Starting Dual Servers: MCP on 3099, CropAPI on 3098...", file=sys.stderr)
    
    # Run both concurrently
    await asyncio.gather(
        server_mcp.serve(),
        server_crop.serve()
    )

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(run_dual_servers())
    except KeyboardInterrupt:
        print("Servers stopped.")


