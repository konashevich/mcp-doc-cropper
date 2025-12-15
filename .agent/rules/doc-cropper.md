---
trigger: always_on
---

# AI Developer Guidelines for MCP Document Cropper

You are an expert software engineer maintaining the `mcp-doc-cropper` project.
This is a **High-Performance Hybrid MCP Server** running on constrained hardware (ARM64 SBC/Rockchip).

## 1. Core Architecture Pattern
- **Hybrid Design**: The server is a single process (`src/server.py`) that acts as BOTH:
    1.  A **FastAPI HTTP Server** (for high-speed binary transfers).
    2.  An **MCP Server** (mounted at `/sse` for agent orchestration).
- **Statelessness**: The server is strictly stateless. Do not store session data.

## 2. Development Rules
### A. No Binary in MCP Protocol
- **NEVER** create MCP tools that accept or return raw file data (base64 strings).
- **Why?** It balloons the Context Window of the consuming Agent and causes crashes.
- **Pattern**: If you need to process a file:
    1.  Create an HTTP endpoint (`@app.post("/endpoint")`) to handle the binary data efficiently.
    2.  Create an MCP tool (`@mcp.tool()`) that simply **generates the terminal command** (e.g., `curl`) for the Agent to call that endpoint.

### B. The "Orchestrator" Pattern
- Tools should be "instructional", not "functional".
- **Example**:
    - **BAD**: `tool.crop_image(base64_data)` -> returns base64
    - **GOOD**: `tool.get_crop_command(path)` -> returns "curl -F file=@path http://.../crop"

### C. Model Loading
- **Lazy Loading**: Use the `get_model()` accessor. Never load heavy models (YOLO, PyTorch) at module level.
- **Robustness**: The server must start even if the model fails to load initially (retry on request).

### D. ZERO TOLERANCE for Fallbacks/Legacy
- **NO Fallback Tools**: Do not create "backup" tools or "legacy" modes. If a feature is upgraded, the old version MUST be deleted effectively immediately.
- **Clean Up**: When refactoring, remove the old code. Do not comment it out. Do not leave it "just in case".
- **Statelessness**: The Agent discovers tools dynamically. It does not need "migration paths". It needs the *current best tool*.
    - **BAD**: Keeping `crop_document_v1` alongside `crop_document_v2`.
    - **GOOD**: Replacing `crop_document` entirely with `get_crop_command`.

## 3. Testing & Verification
- **Manual Start**: The server is often started via `./run_server.sh`.
- **Port Conflicts**: Be aware that `uvicorn` might leave zombie processes. Always check `lsof -i :3099` if startup fails.
- **Verification**: Verify implementation by running a real `curl` command against `localhost:3099`, NOT just unit tests.

## 4. Environment
- **Hardware**: FriendlyELEC CM3588 (ARM64).
- **Paths**: Project lives in `/mnt/merged_ssd/mcp-doc-cropper`.
- **Models**: `/opt/models/yolo/yolo11l-seg.pt` (Do not move or download this; assume it exists).
