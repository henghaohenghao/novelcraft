#!/bin/bash
# 快速测试 vLLM 服务和 LoRA 功能
set -e

VLLM_URL=${VLLM_URL:-"http://localhost:8000"}
STYLE=${1:-gaoxiao}

echo "============================================================"
echo "测试 vLLM 服务"
echo "============================================================"
echo "服务地址: ${VLLM_URL}"
echo "测试风格: ${STYLE}"
echo ""

# 1. 检查服务是否启动
echo "[1/3] 检查服务健康状态..."
if ! curl -s "${VLLM_URL}/health" > /dev/null; then
    echo "❌ 服务未启动或无法访问: ${VLLM_URL}"
    echo ""
    echo "请先启动 vLLM 服务:"
    echo "  bash scripts/deploy_vllm.sh"
    exit 1
fi
echo "  ✓ 服务正常运行"

# 2. 测试基线模型（不加载 LoRA）
echo ""
echo "[2/3] 测试基线模型（无 LoRA）..."
cat > /tmp/test_baseline.json <<EOF
{
  "model": "Qwen/Qwen3-8B",
  "messages": [
    {"role": "system", "content": "你是一位专业的文学风格转换专家。"},
    {"role": "user", "content": "请将以下文本转换为${STYLE}风格：\n\n夜色渐深，街道上的行人越来越少。"}
  ],
  "temperature": 0.7,
  "max_tokens": 200
}
EOF

BASELINE_RESPONSE=$(curl -s "${VLLM_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d @/tmp/test_baseline.json)

echo "  基线模型回复:"
echo "${BASELINE_RESPONSE}" | python -m json.tool 2>/dev/null | grep -A 2 '"content"' | tail -1 || echo "${BASELINE_RESPONSE}"

# 3. 测试微调模型（加载 LoRA）
echo ""
echo "[3/3] 测试微调模型（${STYLE}-style-lora）..."
cat > /tmp/test_lora.json <<EOF
{
  "model": "Qwen/Qwen3-8B",
  "messages": [
    {"role": "system", "content": "你是一位专业的文学风格转换专家。"},
    {"role": "user", "content": "请将以下文本转换为${STYLE}风格：\n\n夜色渐深，街道上的行人越来越少。"}
  ],
  "temperature": 0.7,
  "max_tokens": 200,
  "extra_body": {
    "lora_adapter": "${STYLE}-style-lora"
  }
}
EOF

LORA_RESPONSE=$(curl -s "${VLLM_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d @/tmp/test_lora.json)

echo "  微调模型回复:"
echo "${LORA_RESPONSE}" | python -m json.tool 2>/dev/null | grep -A 2 '"content"' | tail -1 || echo "${LORA_RESPONSE}"

echo ""
echo "============================================================"
echo "测试完成！"
echo "============================================================"
echo ""
echo "下一步: 运行对比实验"
echo "  python benchmark_experiment.py --test-file dataset/benchmark/test_cases.json"

# 清理临时文件
rm -f /tmp/test_baseline.json /tmp/test_lora.json
