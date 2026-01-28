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
- **System Service**: Managed via systemd user service `cropper-mcp.service`.
- **Status**: `systemctl --user status cropper-mcp`
- **Restart**: `systemctl --user restart cropper-mcp`
- **Logs**: `tail -f /mnt/merged_ssd/mcp-doc-cropper/server.log`
- **Verify**: Use real `curl` commands against `localhost:3099/api/crop`.

## 4. Environment
- **Hardware**: FriendlyELEC CM3588 (RK3588 NPU).
- **Paths**: `/mnt/merged_ssd/mcp-doc-cropper`.
- **Model**: `/mnt/merged_ssd/mcp-doc-cropper/yolo11n-seg.rknn` (Pre-loaded on start).
- **Network**: Accessible via `cropper-mcp.local:3099`.

## 5. Mandatory Testing
- **Rule**: After making changes, you MUST restart the service and verify functionality.
- **Scope**: Use `test` folder files: `test/DL1.jpg`, `test/DL2.jpg`.
- **Method**:
    1. Restart service: `systemctl --user restart cropper-mcp`
    2. Call MCP tools from the Agent (this workspace) on the test files.
- **Config**: MCP settings for this workspace are at `/home/pi/.gemini/antigravity/mcp_config.json`.
