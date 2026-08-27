import os
from pathlib import Path

import pytest


RUN_INTEGRATION = os.getenv("RUN_QWEN_INTEGRATION", "0").lower() in {"1", "true", "yes", "on"}

pytestmark = pytest.mark.skipif(
    not RUN_INTEGRATION,
    reason="Set RUN_QWEN_INTEGRATION=1 to run the real Qwen2.5-VL integration test",
)


@pytest.mark.integration
def test_qwen25vl_real_gpu_inference():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA is not available")
    if torch.cuda.get_device_properties(0).total_memory < 8 * 1024**3:
        pytest.skip("Qwen2.5-VL-7B integration requires a GPU with at least 8GB VRAM")
    pytest.importorskip("transformers")
    pytest.importorskip("qwen_vl_utils")

    from ai_training.qwen_vl_adapter import Qwen25VLAdapter

    image_path = Path(__file__).resolve().parents[2] / "data" / "images" / "outfit_0000.jpg"
    assert image_path.exists()
    adapter = Qwen25VLAdapter()
    adapter.load_model()
    result = adapter.describe_image(str(image_path))
    assert adapter.is_loaded
    assert isinstance(result, str)
    assert len(result.strip()) > 0
