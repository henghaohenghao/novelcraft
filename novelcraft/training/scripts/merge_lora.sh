#!/bin/bash
set -e

MODEL=${MODEL:-"Qwen/Qwen3-8B"}
STYLE=${1:-gaoxiao}
ADAPTER="output/${STYLE}-style-lora/$(ls -t output/${STYLE}-style-lora/ 2>/dev/null | grep -E '^checkpoint-' | head -1)"
OUTPUT_DIR="output/${STYLE}-style-merged"

if [ ! -d "${ADAPTER}" ]; then
    echo "错误: 未找到 ${STYLE} 风格的 LoRA 权重"
    echo "请先运行: bash train_${STYLE}.sh"
    exit 1
fi

echo "============================================================"
echo "合并 LoRA 权重: ${ADAPTER}"
echo "输出路径: ${OUTPUT_DIR}"
echo "============================================================"

swift export \
    --model ${MODEL} \
    --adapters ${ADAPTER} \
    --merge_lora true \
    --output_dir ${OUTPUT_DIR}

echo "完成！合并后模型保存在: ${OUTPUT_DIR}"