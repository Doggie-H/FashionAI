from __future__ import annotations

import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.garment_reconstruction import gpu_preflight


if __name__ == "__main__":
    result = gpu_preflight()
    print(json.dumps({
        "eligible": result.eligible,
        "reason": result.reason,
        "gpu_name": result.gpu_name,
        "vram_gb": result.vram_gb,
    }, indent=2))
