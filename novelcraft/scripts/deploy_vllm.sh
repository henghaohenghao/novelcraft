#!/bin/bash

# 部署 vLLM 服务，加载所有风格 LoRA 适配器

set -e

echo "=========================================="
echo "部署 vLLM 风格迁移服务"
echo "=========================================="
echo ""

# 配置
MODEL_NAME="Qwen/Qwen3-8B-Instruct"
HOST="0.0.0.0"
PORT=8000
MAX_LORA_RANK=16

# 检查 vLLM 是否安装
if ! python -c "import vllm" &> /dev/null; then
    echo "错误: vLLM 未安装"
    echo "安装命令: pip install vllm"
    exit 1
fi

# 检查 LoRA 适配器是否存在
echo "检查 LoRA 适配器..."
LORA_MODULES=""
STYLES=("gulong" "caowenxuan" "jinyong" "liubixin" "wangxiaobo" "luxun")

for style in "${STYLES[@]}"; do
    lora_path="outputs/${style}-style-lora/final"
    if [ -d "$lora_path" ]; then
        echo "  ✓ 找到 $style 风格适配器"
        LORA_MODULES="$LORA_MODULES ${style}-style-lora=$lora_path"
    else
        echo "  ✗ 未找到 $style 风格适配器 ($lora_path)"
    fi
done

if [ -z "$LORA_MODULES" ]; then
    echo ""
    echo "错误: 未找到任何 LoRA 适配器"
    echo "请先运行训练脚本: bash scripts/train_all_styles.sh"
    exit 1
fi

# 启动 vLLM 服务
echo ""
echo "启动 vLLM 服务..."
echo "  模型: $MODEL_NAME"
echo "  地址: http://$HOST:$PORT"
echo "  LoRA 适配器: ${#STYLES[@]} 个"
echo ""

python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_NAME" \
    --enable-lora \
    --lora-modules $LORA_MODULES \
    --max-lora-rank $MAX_LORA_RANK \
    --host "$HOST" \
    --port "$PORT" \
    --trust-remote-code

echo ""
echo "vLLM 服务已停止"
