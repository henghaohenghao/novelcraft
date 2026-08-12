#!/bin/bash
set -e

MODEL=${MODEL:-"Qwen/Qwen3-8B"}
STYLE=${1:-gaoxiao}
ADAPTER="output/${STYLE}-style-lora/$(ls -t output/${STYLE}-style-lora/ 2>/dev/null | grep -E '^checkpoint-' | head -1)"

if [ ! -d "${ADAPTER}" ]; then
    echo "错误: 未找到 ${STYLE} 风格的 LoRA 权重"
    echo "请先运行: bash train_${STYLE}.sh"
    echo "或指定目录: ADAPTER=/path/to/lora bash infer_lora.sh ${STYLE}"
    exit 1
fi

echo "============================================================"
echo "风格: ${STYLE}  模型: ${MODEL}"
echo "LoRA: ${ADAPTER}"
echo "输入 exit 退出  |  输入 clear 清屏"
echo "============================================================"

swift infer \
    --model ${MODEL} \
    --adapters ${ADAPTER} \
    --stream true \
    --infer_backend pt \
    --max_new_tokens 2048