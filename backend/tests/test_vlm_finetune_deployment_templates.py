from __future__ import annotations

from pathlib import Path

import yaml


BACKEND_ROOT = Path(__file__).resolve().parents[1]
JOB_TEMPLATE = BACKEND_ROOT / "deployments" / "vlm-finetune-job.yaml.example"
DOCKERFILE = BACKEND_ROOT / "vlm_finetune" / "Dockerfile"
CONFIG = BACKEND_ROOT / "vlm_finetune" / "configs" / "fashion_vlm_lora.example.yaml"


def test_vlm_job_template_is_fail_closed_and_requests_gpu():
    document = next(item for item in yaml.safe_load_all(JOB_TEMPLATE.read_text(encoding="utf-8")) if isinstance(item, dict))
    assert document["kind"] == "Job"
    assert document["spec"]["backoffLimit"] == 0
    pod = document["spec"]["template"]["spec"]
    assert pod["restartPolicy"] == "Never"
    assert pod["serviceAccountName"] == "ai-stylist-vlm-finetune"
    container = pod["containers"][0]
    assert container["resources"]["requests"]["nvidia.com/gpu"] == "1"
    assert any(env["name"] == "RUN_APPROVED" and env["value"] == "1" for env in container["env"])
    assert "preflight_remote_gpu" in container["args"][0]
    assert "validate_manifest" in container["args"][0]
    assert "--execute" in container["args"][0]


def test_vlm_dockerfile_and_example_config_keep_secrets_out_of_source():
    dockerfile = DOCKERFILE.read_text(encoding="utf-8")
    config = CONFIG.read_text(encoding="utf-8")
    assert "USER trainer" in dockerfile
    assert "COPY .env" not in dockerfile
    assert "HF_TOKEN=" not in config
    assert "<licensed-vlm-model-id>" in config
    assert "max_length: null" in config
