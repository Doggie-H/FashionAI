# Choose a CUDA image only after matching the remote provider's NVIDIA driver compatibility matrix.
ARG CUDA_IMAGE=nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04
FROM ${CUDA_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/work/hf-cache \
    TRANSFORMERS_CACHE=/work/hf-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 python3-pip git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY vlm_finetune/requirements.txt /tmp/requirements.txt
# Install torch from the provider/CUDA-compatible index in the CI build command before or together with this layer.
# Do not rely on this image to pick an incompatible PyTorch CUDA wheel automatically.
RUN python3 -m pip install --upgrade pip \
    && python3 -m pip install -r /tmp/requirements.txt

COPY vlm_finetune /app/vlm_finetune
RUN useradd --create-home --uid 10001 trainer \
    && mkdir -p /work \
    && chown -R trainer:trainer /app /work
USER trainer

ENTRYPOINT ["python3", "-m", "vlm_finetune.scripts.train_lora_vlm"]
