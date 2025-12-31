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
    "cropper-mcp",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)


@mcp.tool()
def crop_image(input_path: str, output_path: str = None) -> str:
    """
    Crop a document image directly on the server.
    Use this when calling from a remote machine - files are processed locally.
    
    Args:
        input_path: Absolute path to the source image file on the server.
        output_path: Optional absolute path for the result.
                     If not provided, defaults to <original_name>_cropped.<ext>.
    
    Returns:
        Success message with output path and size, or error/warning message.
    """
    import subprocess
    from pathlib import Path
    
    in_file = Path(input_path).resolve()
    
    if not in_file.exists():
        return f"Error: Input file not found: {in_file}"
    
    input_size = in_file.stat().st_size
    
    if output_path:
        out_file = Path(output_path).resolve()
    else:
        out_file = in_file.with_name(f"{in_file.stem}_cropped{in_file.suffix}")
    
    # Ensure output directory exists
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Execute crop via local API, capture headers to check crop status
    url = "http://127.0.0.1:3099/api/crop"
    result = subprocess.run(
        ["curl", "-s", "-f", "-D", "-", "-F", f"file=@{in_file}", url, "-o", str(out_file)],
        capture_output=True, timeout=60
    )
    
    # Parse headers to check crop status
    headers_output = result.stdout.decode() if result.stdout else ""
    was_cropped = "X-Crop-Status: cropped" in headers_output
    no_detection = "X-Crop-Status: no-detection" in headers_output
    
    # Verify success: curl succeeded AND output exists AND output has reasonable size
    if result.returncode == 0 and out_file.exists():
        output_size = out_file.stat().st_size
        # Check output is valid (at least 1KB and not an error message)
        if output_size > 1024:
            if no_detection:
                return f"Warning: No document detected in {in_file.name} - saved original image to {out_file} ({output_size // 1024} KB)"
            else:
                return f"Success: {out_file} ({output_size // 1024} KB)"
        else:
            # Likely an error response, not an image
            out_file.unlink(missing_ok=True)  # Remove invalid file
            return f"Error: Crop failed for {in_file.name} - output too small ({output_size} bytes), possibly server error"
    else:
        error = result.stderr.decode() if result.stderr else f"curl exit code: {result.returncode}"
        out_file.unlink(missing_ok=True)  # Clean up partial file
        return f"Error: {error}"


@mcp.tool()
def crop_batch(directory_path: str, output_directory: str = None, extensions: list[str] = ["jpg", "jpeg", "png"]) -> str:
    """
    Crop all images in a directory on the server.
    Processes files one-by-one to prevent memory issues.
    
    Args:
        directory_path: Absolute path to folder containing images on the server.
        output_directory: Optional output folder. If None, saves with '_cropped' suffix.
        extensions: File extensions to process (default: jpg, jpeg, png).
    
    Returns:
        Summary of processed files with success/failure/warning status for each.
    """
    import subprocess
    from pathlib import Path
    
    dir_path = Path(directory_path).resolve()
    if not dir_path.is_dir():
        return f"Error: Directory not found: {dir_path}"
    
    url = "http://127.0.0.1:3099/api/crop"
    results = []
    success_count = 0
    warning_count = 0
    fail_count = 0
    
    for ext in extensions:
        # Case-insensitive: check both lower and upper case
        for pattern in [f"*.{ext}", f"*.{ext.upper()}"]:
            for img_file in dir_path.glob(pattern):
                if output_directory:
                    out_dir = Path(output_directory).resolve()
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out_file = out_dir / img_file.name
                else:
                    out_file = img_file.with_name(f"{img_file.stem}_cropped{img_file.suffix}")
                
                try:
                    # Include -D - to capture headers for crop status
                    result = subprocess.run(
                        ["curl", "-s", "-f", "-D", "-", "-F", f"file=@{img_file}", url, "-o", str(out_file)],
                        capture_output=True, timeout=120
                    )
                    
                    # Parse headers to check crop status
                    headers_output = result.stdout.decode() if result.stdout else ""
                    no_detection = "X-Crop-Status: no-detection" in headers_output
                    
                    # Verify: curl OK + file exists + file is valid image size (>1KB)
                    if result.returncode == 0 and out_file.exists() and out_file.stat().st_size > 1024:
                        size_kb = out_file.stat().st_size // 1024
                        if no_detection:
                            results.append(f"⚠ {img_file.name}: no document detected, saved original ({size_kb} KB)")
                            warning_count += 1
                        else:
                            results.append(f"✓ {img_file.name} → {out_file.name} ({size_kb} KB)")
                            success_count += 1
                    else:
                        out_file.unlink(missing_ok=True)  # Remove invalid/partial file
                        results.append(f"✗ {img_file.name}: crop failed (invalid output)")
                        fail_count += 1
                        
                except subprocess.TimeoutExpired:
                    out_file.unlink(missing_ok=True)
                    results.append(f"✗ {img_file.name}: timeout")
                    fail_count += 1
                except Exception as e:
                    results.append(f"✗ {img_file.name}: {str(e)}")
                    fail_count += 1
    
    if not results:
        return f"No images found in {dir_path} with extensions: {extensions}"
    
    summary = f"Batch complete: {success_count} cropped, {warning_count} no-detection, {fail_count} failed\n"
    return summary + "\n".join(results)


@mcp.tool()
def get_crop_command(input_path: str, output_path: str = None) -> str:
    """
    [LEGACY - use crop_image instead]
    Generates the terminal command to crop a local document image.
    Only use if agent runs on the SAME machine as the server.
    
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

    # 2. Construct Server URL (Pointing to the Crop API)
    url = f"http://{SERVER_IP}:3099/api/crop"


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
    url = f"http://{SERVER_IP}:3099/api/crop"
    
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
def run_crop(img: np.ndarray, model) -> tuple[np.ndarray, bool]:
    """
    Core cropping logic using NPU backend.
    Returns: (image, was_cropped) tuple
    """
    # Run inference
    # Returns list of dicts: [{'box': [x1,y1,x2,y2], 'score': float, 'class_id': int}, ...]
    results = model.run(img)
    
    if not results:
        print("No objects detected. Returning original.", file=sys.stderr)
        return img, False

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

    return img[y1:y2, x1:x2], True

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
    Returns: image/jpeg with X-Crop-Status header indicating if crop occurred.
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
            
        cropped_img, was_cropped = run_crop(img, model)
        
        _, buffer = cv2.imencode('.jpg', cropped_img)
        
        # Return with header indicating crop status
        headers = {"X-Crop-Status": "cropped" if was_cropped else "no-detection"}
        return Response(content=buffer.tobytes(), media_type="image/jpeg", headers=headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Server Execution ---
async def run_dual_servers():
    import uvicorn
    import contextlib
    from starlette.applications import Starlette
    from starlette.routing import Mount
    
    # Create combined app with both MCP (streamable-http) and Crop API
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette):
        async with mcp.session_manager.run():
            yield
    
    # Combined Starlette app:
    # - /mcp -> MCP Streamable HTTP endpoint
    # - /api/crop -> Direct crop API
    
    # Set streamable_http_path to root so endpoint is at /mcp not /mcp/mcp
    mcp.settings.streamable_http_path = "/"
    
    combined_app = Starlette(
        routes=[
            Mount("/mcp", app=mcp.streamable_http_app()),
            Mount("/api", app=crop_api_app),
        ],
        lifespan=lifespan,
    )
    
    # Single server on port 3099
    config = uvicorn.Config(app=combined_app, host="0.0.0.0", port=3099, log_config=None)
    server = uvicorn.Server(config)

    print("Starting Server on port 3099:", file=sys.stderr)
    print("  - MCP endpoint: http://0.0.0.0:3099/mcp", file=sys.stderr)
    print("  - Crop API: http://0.0.0.0:3099/api/crop", file=sys.stderr)
    
    await server.serve()

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(run_dual_servers())
    except KeyboardInterrupt:
        print("Servers stopped.")


