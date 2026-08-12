#!/bin/bash

# 一键训练所有风格的 LoRA 适配器

set -e

echo "=========================================="
echo "NovelCraft 风格迁移模型训练"
echo "=========================================="
echo ""

# 定义风格列表
declare -A STYLES=(
    ["gulong"]="古龙"
    ["caowenxuan"]="曹文轩"
    ["jinyong"]="金庸"
    ["liubixin"]="刘慈欣"
    ["wangxiaobo"]="王小波"
    ["luxun"]="鲁迅"
)

# 检查 Python 环境
if ! command -v python &> /dev/null; then
    echo "错误: Python 未安装"
    exit 1
fi

# 检查 LLaMA Factory
if ! command -v llamafactory-cli &> /dev/null; then
    echo "警告: LLaMA Factory 未安装"
    echo "正在安装..."
    pip install llama-factory
fi

# 创建必要的目录
mkdir -p data/style_transfer
mkdir -p outputs
mkdir -p logs

# 训练每个风格
for style_id in "${!STYLES[@]}"; do
    style_name="${STYLES[$style_id]}"

    echo ""
    echo "=========================================="
    echo "训练风格: $style_name ($style_id)"
    echo "=========================================="

    # 生成训练配置和示例数据
    python scripts/train_style_model.py \
        --style-name "$style_name" \
        --style-id "$style_id" \
        --generate-sample \
        --num-samples 500

    # 开始训练
    echo ""
    echo "开始训练 $style_name 风格..."

    llamafactory-cli train "outputs/${style_id}-style-lora/train_config.yaml" \
        2>&1 | tee "logs/${style_id}_training.log"

    echo ""
    echo "✓ $style_name 风格训练完成"
done

echo ""
echo "=========================================="
echo "所有风格训练完成！"
echo "=========================================="
echo ""
echo "LoRA 适配器保存位置:"
for style_id in "${!STYLES[@]}"; do
    echo "  - outputs/${style_id}-style-lora/final"
done

echo ""
echo "下一步: 部署 vLLM 服务"
echo "  bash scripts/deploy_vllm.sh"
echo ""
