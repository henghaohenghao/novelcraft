#!/bin/bash
set -e

MODEL=${MODEL:-"Qwen/Qwen3-8B"}
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-8000}
GPU=${CUDA_VISIBLE_DEVICES:-0}

echo "============================================================"
echo "部署原始 Qwen3-8B 基线模型 (无 LoRA)"
echo "============================================================"
echo ""
echo "模型: ${MODEL}"
echo "地址: http://${HOST}:${PORT}"
echo "GPU: ${GPU}"
echo ""

export CUDA_VISIBLE_DEVICES=${GPU}

swift deploy \
    --model "${MODEL}" \
    --infer_backend pt \
    --host "${HOST}" \
    --port "${PORT}" \
    --max_new_tokens 2048