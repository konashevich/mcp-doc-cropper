# MCP Document Cropper

An MCP server that provides document boundary detection and cropping capabilities using YOLOv11 authentication. It is designed to run on ARM64 Linux devices (like Rockchip RK3588) and serve other machines on the local network.

## Features

- **Document Cropping**: Detects document boundaries in images and crops them automatically.
- **YOLOv11 Powered**: Uses a state-of-the-art YOLOv11 Large Segmentation model (`yolo11l-seg.pt`).
- **Hybrid Architecture**:
    - **MCP Mode**: For chat/instruction based interaction.
    - **HTTP Mode**: High-performance `POST /crop` endpoint for zero-latency file processing.

## Prerequisites

- **Python 3.10+**
- **Hardware**: NPU acceleration recommended (e.g., Rockchip RK3588), though it runs on CPU.
- **Model File**: Requires `yolo11l-seg.pt` at `/opt/models/yolo/yolo11l-seg.pt`.

## Installation

1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd mcp-doc-cropper
   ```

2. **Set up Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install ultralytics opencv-python numpy mcp
   ```

## Usage & Configuration

## Usage & Configuration

This server runs in a **stateless, dual-port** configuration.

### 1. Start the Server
Run the server on your Linux machine:
```bash
./run_server.sh
```
This starts TWO services:
1.  **MCP Server (Port 3099)**: Handles AI Agent connections (SSE).
2.  **Crop API (Port 3098)**: Handles high-speed file uploads.

### 2. Connect from VS Code / Cursor / Claude
Configure your `mcp.json` (or extension settings) to connect via **SSE**.

**Critical Settings:**
- **URL**: `http://<IP>:3099/sse` (Use `127.0.0.1` if VS Code is on the same machine).
- **Type**: `"sse"` (This is mandatory to prevent it from trying to run a local process).

#### Example `mcp.json`:
```json
{
  "mcpServers": {
    "doc-cropper": {
      "type": "sse",
      "url": "http://127.0.0.1:3099/sse", 
      "transport": "sse"
    }
  }
}
```

### 3. Usage (Zero-Step Flow)
1.  The Agent connects to the MCP server.
2.  The Agent sees the `get_crop_command` tool.
3.  The Agent requests to crop a file.
4.  The Tool gives the Agent a `curl` command pointing to **Port 3098**.
    ```bash
    curl -F file=@doc.jpg http://192.168.1.114:3098/crop -o doc_cropped.jpg
    ```
5.  The Agent executes `curl` in the terminal. **Done.**

*Note: This architecture bypasses the LLM context window entirely.*


## API

### Tool: `crop_document`
- **Input**: `image_base64` (string) - Base64 encoded image data.
- **Output**: Base64 encoded string of the cropped document.
