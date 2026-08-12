#!/bin/bash
# 一键训练所有风格的 LoRA
# 用法:
#   bash train_all.sh                    # 默认配置
#   MODEL=/path/to/model bash train_all.sh  # 指定模型
#   NUM_GPUS=2 bash train_all.sh         # 多卡训练

set -e

MODEL=${MODEL:-"Qwen/Qwen3-8B"}
NUM_GPUS=${NUM_GPUS:-1}
GPUS=${CUDA_VISIBLE_DEVICES:-0}

echo "============================================================"
echo "批量训练所有风格 LoRA"
echo "模型: ${MODEL}  GPU: ${GPUS} (数量: ${NUM_GPUS})"
echo "============================================================"

# 训练搞笑风格
echo -e "\n>>> [1/3] 训练搞笑风格"
CUDA_VISIBLE_DEVICES=${GPUS} NUM_GPUS=${NUM_GPUS} MODEL=${MODEL} bash "$(dirname "$0")/train_gaoxiao.sh"

# 训练古风风格
echo -e "\n>>> [2/3] 训练古风风格"
CUDA_VISIBLE_DEVICES=${GPUS} NUM_GPUS=${NUM_GPUS} MODEL=${MODEL} bash "$(dirname "$0")/train_gufeng.sh"

# 训练言情风格
echo -e "\n>>> [3/3] 训练言情风格"
CUDA_VISIBLE_DEVICES=${GPUS} NUM_GPUS=${NUM_GPUS} MODEL=${MODEL} bash "$(dirname "$0")/train_yanqing.sh"

echo ""
echo "============================================================"
echo "所有风格训练完成！"
echo "输出目录:"
echo "  output/gaoxiao-style-lora/"
echo "  output/gufeng-style-lora/"
echo "  output/yanqing-style-lora/"
echo "============================================================"
