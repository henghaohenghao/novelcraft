#!/bin/bash
# 一键运行完整对比实验流程
set -e

VLLM_URL=${VLLM_URL:-"http://localhost:8000"}
TEST_FILE=${TEST_FILE:-"dataset/benchmark/test_cases.json"}

echo "============================================================"
echo "风格迁移对比实验 - 完整流程"
echo "============================================================"
echo ""

# Step 1: 检查测试集
echo "[Step 1/5] 检查测试集..."
if [ ! -f "${TEST_FILE}" ]; then
    echo "  ⚠️  测试集不存在: ${TEST_FILE}"
    echo "  正在生成测试集..."
    python prepare_test_set.py --test-ratio 0.1 --benchmark-samples 10

    if [ ! -f "${TEST_FILE}" ]; then
        echo "  ❌ 测试集生成失败"
        exit 1
    fi
fi
echo "  ✓ 测试集就绪: ${TEST_FILE}"

# Step 2: 检查 vLLM 服务
echo ""
echo "[Step 2/5] 检查 vLLM 服务..."
if ! curl -s "${VLLM_URL}/health" > /dev/null 2>&1; then
    echo "  ❌ vLLM 服务未启动"
    echo ""
    echo "请在另一个终端启动服务:"
    echo "  bash scripts/deploy_vllm.sh"
    echo ""
    echo "或后台启动:"
    echo "  nohup bash scripts/deploy_vllm.sh > vllm.log 2>&1 &"
    exit 1
fi
echo "  ✓ vLLM 服务正常运行"

# Step 3: 快速测试
echo ""
echo "[Step 3/5] 快速测试 LoRA 加载..."
bash scripts/test_deployment.sh gaoxiao > /tmp/deployment_test.log 2>&1
if [ $? -ne 0 ]; then
    echo "  ❌ 服务测试失败，查看日志: /tmp/deployment_test.log"
    exit 1
fi
echo "  ✓ LoRA 加载正常"

# Step 4: 运行对比实验
echo ""
echo "[Step 4/5] 运行对比实验..."
echo "  这可能需要几分钟，请耐心等待..."
python benchmark_experiment.py \
    --test-file ${TEST_FILE} \
    --vllm-url ${VLLM_URL}

# 获取最新的结果文件
RESULT_FILE=$(ls -t results/benchmark_*.json 2>/dev/null | head -1)

if [ -z "${RESULT_FILE}" ]; then
    echo "  ❌ 未找到实验结果文件"
    exit 1
fi

echo "  ✓ 实验完成: ${RESULT_FILE}"

# Step 5: 计算评估指标
echo ""
echo "[Step 5/5] 计算评估指标..."
python metrics.py ${RESULT_FILE}

EVAL_FILE=$(ls -t results/evaluation_*.json 2>/dev/null | head -1)

# Step 6: 生成可视化报告
echo ""
echo "[Bonus] 生成可视化报告..."
python visualize_results.py \
    ${EVAL_FILE} \
    --benchmark ${RESULT_FILE} \
    --output results/report.html \
    --markdown

echo ""
echo "============================================================"
echo "实验完成！"
echo "============================================================"
echo ""
echo "查看结果:"
echo "  原始数据:     ${RESULT_FILE}"
echo "  评估指标:     ${EVAL_FILE}"
echo "  HTML 报告:    results/report.html"
echo "  Markdown 报告: results/report.md"
echo ""
echo "在浏览器中打开:"
echo "  start results/report.html     # Windows"
echo "  open results/report.html      # macOS"
echo "  xdg-open results/report.html  # Linux"
