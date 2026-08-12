# vLLM 部署和测试指南

## 快速开始

### 1. 训练 LoRA 模型（如已训练可跳过）

```bash
# 训练单个风格
bash scripts/train_gaoxiao.sh

# 或批量训练所有风格
bash scripts/train_all.sh
```

### 2. 部署 vLLM 服务

```bash
# 前台启动（推荐调试时使用）
bash scripts/deploy_vllm.sh

# 后台启动（推荐正式测试时使用）
nohup bash scripts/deploy_vllm.sh > logs/vllm.log 2>&1 &

# 查看日志
tail -f logs/vllm.log
```

**启动成功标志：**
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

### 3. 测试服务

```bash
# 测试服务是否正常
bash scripts/test_deployment.sh gaoxiao

# 测试其他风格
bash scripts/test_deployment.sh gufeng
bash scripts/test_deployment.sh yanqing
```

**预期输出：**
```
============================================================
测试 vLLM 服务
============================================================
[1/3] 检查服务健康状态...
  ✓ 服务正常运行

[2/3] 测试基线模型（无 LoRA）...
  基线模型回复: [生成的文本]

[3/3] 测试微调模型（gaoxiao-style-lora）...
  微调模型回复: [生成的文本]

============================================================
测试完成！
============================================================
```

### 4. 运行对比实验

```bash
# 一键运行完整流程（推荐）
bash scripts/run_benchmark.sh

# 或手动运行
python benchmark_experiment.py --test-file dataset/benchmark/test_cases.json
python metrics.py results/benchmark_*.json
python visualize_results.py results/evaluation_*.json --benchmark results/benchmark_*.json
```

## 详细说明

### deploy_vllm.sh - 部署脚本

**功能：**
- 自动扫描已训练的 LoRA 模型
- 启动支持多 LoRA 动态加载的 vLLM 服务
- 配置最优推理参数

**环境变量配置：**
```bash
# 使用不同的基础模型
MODEL="Qwen/Qwen3-8B" bash scripts/deploy_vllm.sh

# 修改端口
PORT=8001 bash scripts/deploy_vllm.sh

# 指定 GPU
CUDA_VISIBLE_DEVICES=1 bash scripts/deploy_vllm.sh

# 调整最大长度
MAX_MODEL_LEN=4096 bash scripts/deploy_vllm.sh
```

**vLLM 参数说明：**
- `--enable-lora`: 启用 LoRA 支持
- `--lora-modules`: 注册 LoRA 适配器（格式：`名称=路径`）
- `--max-lora-rank`: 最大 LoRA rank（需 ≥ 训练时的 rank）
- `--max-model-len`: 最大序列长度
- `--gpu-memory-utilization`: GPU 显存使用率（0-1）

### test_deployment.sh - 测试脚本

**功能：**
- 检查服务健康状态
- 对比基线模型和微调模型的输出
- 验证 LoRA 是否正确加载

**使用方法：**
```bash
# 测试默认风格（gaoxiao）
bash scripts/test_deployment.sh

# 测试指定风格
bash scripts/test_deployment.sh gufeng

# 使用不同的服务地址
VLLM_URL="http://192.168.1.100:8000" bash scripts/test_deployment.sh
```

### run_benchmark.sh - 一键实验脚本

**功能：**
- 自动检查依赖（测试集、vLLM 服务）
- 运行完整对比实验
- 计算评估指标
- 生成可视化报告

**使用方法：**
```bash
# 使用默认配置
bash scripts/run_benchmark.sh

# 自定义配置
TEST_FILE="dataset/benchmark/custom_test.json" \
VLLM_URL="http://localhost:8001" \
bash scripts/run_benchmark.sh
```

## 目录结构

```
novelcraft/training/
├── scripts/
│   ├── train_gaoxiao.sh      # 训练搞笑风格 LoRA
│   ├── train_gufeng.sh       # 训练古风风格 LoRA
│   ├── train_yanqing.sh      # 训练言情风格 LoRA
│   ├── train_all.sh          # 批量训练所有风格
│   ├── deploy_vllm.sh        # 部署 vLLM 服务 ⭐ 新增
│   ├── test_deployment.sh    # 测试部署 ⭐ 新增
│   └── run_benchmark.sh      # 一键运行实验 ⭐ 新增
├── output/                   # 训练输出目录
│   ├── gaoxiao-style-lora/
│   │   └── checkpoint-XXX/   # LoRA 权重
│   ├── gufeng-style-lora/
│   └── yanqing-style-lora/
├── dataset/
│   └── benchmark/
│       └── test_cases.json   # 测试集
└── results/                  # 实验结果
    ├── benchmark_*.json      # 原始数据
    ├── evaluation_*.json     # 评估指标
    └── report.html           # 可视化报告
```

## 常见问题

### Q1: vLLM 启动失败，显示 CUDA out of memory

**原因：** GPU 显存不足

**解决方法：**
```bash
# 降低显存使用率
MAX_MODEL_LEN=4096 bash scripts/deploy_vllm.sh

# 或在 deploy_vllm.sh 中修改 --gpu-memory-utilization 参数（默认 0.9）
```

### Q2: 找不到 LoRA 模型

**原因：** 未训练或训练输出路径不匹配

**解决方法：**
```bash
# 检查输出目录
ls -la output/gaoxiao-style-lora/

# 重新训练
bash scripts/train_gaoxiao.sh
```

### Q3: benchmark 实验报错 "Connection refused"

**原因：** vLLM 服务未启动或端口不匹配

**解决方法：**
```bash
# 检查服务是否运行
curl http://localhost:8000/health

# 如果未运行，启动服务
bash scripts/deploy_vllm.sh
```

### Q4: 测试结果显示基线和微调输出几乎相同

**可能原因：**
1. LoRA 未正确加载
2. 训练不充分
3. 测试样本与训练数据分布差异太大

**排查步骤：**
```bash
# 1. 验证 LoRA 加载
bash scripts/test_deployment.sh gaoxiao

# 2. 检查训练日志
cat output/gaoxiao-style-lora/logging.jsonl | tail -20

# 3. 使用训练集中的样本测试
```

## 性能优化

### 推理速度优化

```bash
# 使用 FP16（如果 GPU 支持）
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-8B \
    --dtype float16 \
    ...

# 增加 batch size（仅影响吞吐量，不影响延迟）
python -m vllm.entrypoints.openai.api_server \
    --max-num-batched-tokens 8192 \
    ...
```

### 显存优化

```bash
# 减少 max_model_len
MAX_MODEL_LEN=2048 bash scripts/deploy_vllm.sh

# 降低 KV cache 显存占用
python -m vllm.entrypoints.openai.api_server \
    --gpu-memory-utilization 0.8 \
    ...
```

## 进阶使用

### 多卡部署

```bash
# 使用 2 张 GPU
CUDA_VISIBLE_DEVICES=0,1 bash scripts/deploy_vllm.sh

# vLLM 会自动启用 tensor parallel
```

### 远程部署

```bash
# 服务器上启动
bash scripts/deploy_vllm.sh

# 本地测试
VLLM_URL="http://服务器IP:8000" bash scripts/test_deployment.sh
```

### 自定义测试集

```python
# 创建自定义测试集
import json

custom_tests = {
    "gaoxiao": [
        {"text": "你的测试文本1", "reference": "可选的参考答案"},
        {"text": "你的测试文本2"},
    ],
    # ...
}

with open("dataset/benchmark/custom_test.json", "w", encoding="utf-8") as f:
    json.dump(custom_tests, f, ensure_ascii=False, indent=2)
```

```bash
# 使用自定义测试集
python benchmark_experiment.py --test-file dataset/benchmark/custom_test.json
```

## 监控和调试

### 监控 GPU 使用

```bash
# 实时监控
watch -n 1 nvidia-smi

# 查看详细信息
nvidia-smi dmon -s pucvmet
```

### 查看 vLLM 日志

```bash
# 前台启动时直接显示
bash scripts/deploy_vllm.sh

# 后台启动时查看日志文件
tail -f logs/vllm.log
```

### 调试请求

```bash
# 手动发送测试请求
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B",
    "messages": [{"role": "user", "content": "测试"}],
    "extra_body": {"lora_adapter": "gaoxiao-style-lora"}
  }' | python -m json.tool
```
