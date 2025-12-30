import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://cropper-mcp.local:3099"
SSE_URL = f"{BASE_URL}/sse"

def run_client():
    print(f"Connecting to {SSE_URL}...")
    try:
        req = urllib.request.Request(SSE_URL)
        with urllib.request.urlopen(req) as response:
            endpoint_url = None
            for line in response:
                line = line.decode('utf-8').strip()
                if not line:
                    continue
                if line.startswith("event: endpoint"):
                    # Next line should be data
                    continue
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data.startswith("/messages"):
                        endpoint_path = data
                        endpoint_url = f"{BASE_URL}{endpoint_path}"
                        print(f"Endpoint found: {endpoint_url}")
                        break
        
        if endpoint_url:
            # Send initialize
            print("Sending initialize request...")
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "debug-client", "version": "1.0"}
                }
            }
            json_payload = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(endpoint_url, data=json_payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as res:
                print(f"Initialize response: {res.status} {res.read().decode('utf-8')}")
            
            # Send initialized notification
            payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            json_payload = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(endpoint_url, data=json_payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as res:
                pass 

            # List tools
            print("Sending tools/list request...")
            payload = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list"
            }
            json_payload = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(endpoint_url, data=json_payload, headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req) as res:
                print(f"Tools list response: {res.status} {res.read().decode('utf-8')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_client()
