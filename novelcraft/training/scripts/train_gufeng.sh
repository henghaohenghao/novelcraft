#!/bin/bash
set -e

MODEL=${MODEL:-"Qwen/Qwen3-8B"}
STYLE="gufeng"
DATASET="dataset/gufeng_train.jsonl"
OUTPUT_DIR="output/${STYLE}-style-lora"
GPUS=${CUDA_VISIBLE_DEVICES:-0}
NUM_GPUS=${NUM_GPUS:-1}

echo "============================================================"
echo "训练风格: ${STYLE}  模型: ${MODEL}  GPU: ${GPUS}"
echo "============================================================"

export CUDA_VISIBLE_DEVICES=${GPUS}
[ "${NUM_GPUS}" -gt 1 ] && export NPROC_PER_NODE=${NUM_GPUS}

swift sft \
    --model ${MODEL} \
    --train_type lora \
    --dataset $(cd .. && pwd)/${DATASET} \
    --lora_rank 8 \
    --lora_alpha 32 \
    --target_modules all-linear \
    --torch_dtype bfloat16 \
    --num_train_epochs 3 \
    --per_device_train_batch_size 1 \
    --gradient_accumulation_steps 16 \
    --learning_rate 1e-4 \
    --warmup_ratio 0.05 \
    --max_length 2048 \
    --output_dir ${OUTPUT_DIR} \
    --save_strategy epoch \
    --save_total_limit 3 \
    --logging_steps 10 \
    --gradient_checkpointing true \
    ${DEEPSPEED:+--deepspeed ${DEEPSPEED}}

echo "完成！模型保存在: ${OUTPUT_DIR}"