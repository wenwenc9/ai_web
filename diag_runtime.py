import requests
import json

BASE = "http://localhost:9001/ag-ui"

# 1) AG-UI 标准 runtime info 端点
for method, url, body in [
    ("POST", f"{BASE}/runtime-info", {"protocolVersion": 1, "metadata": {}, "authentications": []}),
    ("POST", f"{BASE}/runtime-info", {}),
    ("GET", f"{BASE}/runtime-info", None),
    ("GET", BASE, None),
    ("POST", BASE, {"runId": "x", "threadId": "t", "messages": []}),
]:
    try:
        if body is None:
            r = requests.request(method, url, timeout=15)
        else:
            r = requests.request(method, url, json=body, timeout=15)
        print(f"[{method} {url}] -> {r.status_code}")
        txt = r.text
        print("   ", txt[:500].replace("\n", " "))
    except Exception as e:
        print(f"[{method} {url}] -> ERROR {e}")
    print()
