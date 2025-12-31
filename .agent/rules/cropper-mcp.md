---
trigger: always_on
---

# AI Developer Guidelines for MCP Document Cropper

You are maintaining `mcp-doc-cropper`, a **High-Performance Hybrid MCP Server** on ARM64/Rockchip.

## 1. Architecture: Hybrid & Stateless
- **Single Process**: Acts as both a **FastAPI HTTP Server** (binary transfer) and **MCP Server** (`/mcp`).
- **Stateless**: Strictly no session data storage.

## 2. Development Rules
### A. No Binary in MCP (CRITICAL)
- **NEVER** handle raw file data (base64) in MCP tools to avoid context bloat.
- **Pattern**: Create an HTTP endpoint for binary processing. The MCP tool just generates a terminal command (e.g., `curl`) to call it.

### B. The "Orchestrator" Pattern
- Tools are "instructional", not "functional".
- **Yes**: `tool.get_crop_command(path)` -> "curl ..."
- **No**: `tool.crop_image(data)` -> base64

### C. Resource Management
- **Lazy Loading**: Use `get_model()`. Never load heavy models at module level.
- **Robustness**: Server must start even if model loading fails initially.

### D. Zero Tolerance for Legacy
- **No Fallbacks**: Delete old versions immediately upon upgrade.
- **Clean Code**: No commented-out code. The agent needs the *current best tool*.

## 3. Operations
- **Start**: `./run_server.sh`. Watch for zombie processes on port 3099 (`lsof -i :3099`).
- **Verify**: Use real `curl` commands against `localhost:3099`.

## 4. Environment
- **Hardware**: FriendlyELEC CM3588 (ARM64).
- **Paths**: `/mnt/merged_ssd/mcp-doc-cropper`.
- **Models**: `/opt/models/yolo/yolo11l-seg.pt` (Assume exists).

## 5. Mandatory Testing
- **Rule**: After making changes, you MUST start the server and verify functionality using the actual MCP client in this workspace.
- **Scope**: Use `test` folder files:
    - `test/DL1.jpg`
    - `test/DL2.jpg`
- **Method**:
    1. Start server: `./run_server.sh`
    2. Call MCP tools from the Agent (this workspace) on the test files.
- **Config**: MCP settings for this workspace are at `/home/pi/.gemini/antigravity/mcp_config.json`.
