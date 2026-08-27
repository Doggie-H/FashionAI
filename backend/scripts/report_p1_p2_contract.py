from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from main import app


PREFIXES = ("/workflow", "/review-tasks")


if __name__ == "__main__":
    schema = app.openapi()
    report: list[dict[str, object]] = []
    for path, operations in sorted(schema["paths"].items()):
        if not path.startswith(PREFIXES):
            continue
        for method, details in sorted(operations.items()):
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            report.append({
                "method": method.upper(),
                "path": path,
                "summary": details.get("summary"),
                "tags": details.get("tags", []),
                "response_codes": sorted(details.get("responses", {}).keys()),
                "request_body": bool(details.get("requestBody")),
                "parameters": [parameter.get("name") for parameter in details.get("parameters", [])],
            })
    print(json.dumps(report, indent=2, ensure_ascii=False))
