#!/bin/bash
set -e

# ============================================================
# vLLM 加速部署风格迁移服务（通过 ms-swift 统一入口）
#
# 改造说明：
#   原版用 --infer_backend pt（PyTorch 原生），慢
#   新版用 --infer_backend vllm --merge_lora true，swift 自动：
#     1. 合并 LoRA 权重到基础模型
#     2. 用 vLLM 启动 OpenAI 兼容服务
#   性能：吞吐 5~10x，首 token 延迟显著降低（PagedAttention + 连续批处理）
#
# 前置条件：
#   1. pip install ms-swift -U
#   2. pip install vllm      # vLLM 必须，按 CUDA 版本选
#   3. GPU 可用（vLLM 不支持 CPU）
#   4. 已运行 train_*.sh 训练好 LoRA
# ============================================================

MODEL=${MODEL:-"/root/autodl-tmp/modelscope/hub/models/Qwen/Qwen3-8B"}
HOST=${HOST:-"0.0.0.0"}
PORT=${PORT:-6006}
GPU=${CUDA_VISIBLE_DEVICES:-0}
# 要部署的风格，默认全部；可单选：STYLE=gaoxiao bash deploy_vllm.sh
STYLE=${STYLE:-""}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADAPTERS=""

echo "============================================================"
echo "vLLM 部署风格迁移服务（ms-swift 入口）"
echo "============================================================"

# 自动查找训练好的 LoRA checkpoint
STYLES=("gaoxiao" "gufeng" "yanqing")
[ -n "${STYLE}" ] && STYLES=("${STYLE}")

for style in "${STYLES[@]}"; do
    lora_dir="${SCRIPT_DIR}/output/${style}-style-lora"
    if [ -d "$lora_dir" ]; then
        # 排除 *-merged 目录（那是之前 --merge_lora 生成的完整模型，不是 LoRA adapter）
        ckpt=$(ls -td ${lora_dir}/*/checkpoint-* ${lora_dir}/checkpoint-* 2>/dev/null | grep -v -- '-merged$' | head -1)
        if [ -n "$ckpt" ]; then
            echo "  [OK] ${style}: ${ckpt}"
            ADAPTERS="${ADAPTERS} ${ckpt}"
        else
            echo "  [--] ${style}: 目录存在但无 checkpoint"
        fi
    else
        echo "  [--] ${style}: 未训练"
    fi
done

if [ -z "$ADAPTERS" ]; then
    echo ""
    echo "错误: 未找到任何 LoRA 适配器"
    echo "请先运行: bash train_gaoxiao.sh"
    exit 1
fi

echo ""
echo "模型: ${MODEL}"
echo "地址: http://${HOST}:${PORT}"
echo "GPU:  ${GPU}"
echo ""

export CUDA_VISIBLE_DEVICES=${GPU}

# ----- 核心改动：pt -> vllm -----
# --infer_backend vllm       : 使用 vLLM 推理引擎
# --adapters                 : 直接加载 LoRA adapter（不合并，避免写 16GB 到磁盘）
# --vllm_max_model_len 8192  : 上下文长度，风格迁移 4k~8k 够用
# --max_new_tokens 2048      : 单次最大生成 token 数
# --vllm_gpu_memory_utilization 0.9 : 显存占用比例，按服务器情况调整
#
# 注意1：不传 --merge_lora true，避免合并后模型写盘占用 16GB 系统盘空间
#        vLLM 会动态加载 LoRA adapter，性能损失很小（约 5%），但省磁盘
# 注意2：不传 --trust_remote_code，swift 不识别该参数（vLLM 原生参数名）
#        Qwen3 是 swift 官方支持模型，swift 内部会自动处理远程代码信任
#
# swift deploy 会自动暴露 OpenAI 兼容的 /v1/chat/completions 接口，
# 后端 style_transfer_service.py 调用方式完全不变。
exec swift deploy \
    --model ${MODEL} \
    --adapters ${ADAPTERS} \
    --infer_backend vllm \
    --host ${HOST} \
    --port ${PORT} \
    --max_new_tokens 16384 \
    --vllm_max_model_len 16384 \
    --vllm_gpu_memory_utilization 0.9
