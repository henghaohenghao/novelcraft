# 风格迁移训练与实验流程

从数据准备到模型训练、部署测试、评估对比的完整流程。

## 流程概览

```
数据准备 → 模型训练 → 部署服务 → 基准测试 → 评估对比
```

---

## 1. 数据准备

使用 `prepare_dataset.py` 从小说原始数据生成风格迁移训练集。

脚本会调用 DeepSeek API 将原文改写为通用风格，构造「通用风格 → 目标风格」的训练对。

```bash
cd training

# 生成所有风格的数据集（搞笑、古风、言情）
python prepare_dataset.py --style all

# 只生成某个风格的数据集
python prepare_dataset.py --style gaoxiao
python prepare_dataset.py --style gufeng
python prepare_dataset.py --style yanqing

# 指定单个输入文件
python prepare_dataset.py --style gaoxiao --input-file data/gaoxiao/novel.jsonl

# 测试模式（每个风格只生成 10 条样本，快速验证流程）
python prepare_dataset.py --style all --test

# 限制样本数量
python prepare_dataset.py --style gaoxiao --max-samples 100
```

**输出**：`dataset/{style}_train_{timestamp}.jsonl` 和 `dataset/{style}_test_{timestamp}.jsonl`

**前提**：
- `data/{style}/` 目录下需要有原始小说 jsonl 文件
- DeepSeek API Key 已内置于脚本中

---

## 2. 模型训练

使用 swift 框架对 Qwen3-8B 进行 LoRA 微调，每种风格单独训练一个适配器。

```bash
cd training

# 训练搞笑风格 LoRA
bash scripts/train_gaoxiao.sh

# 训练言情风格 LoRA
bash scripts/train_yanqing.sh

# 训练古风风格 LoRA
bash scripts/train_gufeng.sh
```

**可配置环境变量**：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL` | `Qwen/Qwen3-8B` | 基座模型 |
| `CUDA_VISIBLE_DEVICES` | `0` | 使用的 GPU |
| `NUM_GPUS` | `1` | GPU 数量（多卡时自动启用分布式） |
| `DEEPSPEED` | 无 | DeepSpeed 配置文件路径（可选） |

示例：

```bash
# 指定 GPU 和模型
CUDA_VISIBLE_DEVICES=1 MODEL=Qwen/Qwen3-8B bash scripts/train_gaoxiao.sh

# 多卡训练
NUM_GPUS=2 CUDA_VISIBLE_DEVICES=0,1 bash scripts/train_gaoxiao.sh

# 使用 DeepSpeed
DEEPSPEED=ds_config.json bash scripts/train_gaoxiao.sh
```

**输出**：`output/{style}-style-lora/checkpoint-*`

**训练参数**：LoRA rank=8, alpha=32, 3 epochs, lr=1e-4, max_length=2048

---

## 3. 部署服务

使用 swift deploy 将基座模型和所有训练好的 LoRA 适配器一起部署为 OpenAI 兼容 API 服务。

```bash
cd training

# 启动部署服务（自动扫描 output/ 下的 LoRA checkpoint）
bash scripts/deploy_vllm.sh
```

**可配置环境变量**：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODEL` | `Qwen/Qwen3-8B` | 基座模型 |
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8000` | 监听端口 |
| `CUDA_VISIBLE_DEVICES` | `0` | 使用的 GPU |

示例：

```bash
# 指定端口和 GPU
PORT=8080 CUDA_VISIBLE_DEVICES=0 bash scripts/deploy_vllm.sh

# 后台运行
nohup bash scripts/deploy_vllm.sh > vllm.log 2>&1 &
```

**部署完成后**，服务提供 OpenAI 兼容接口：
- 模型列表：`GET http://localhost:8000/v1/models`
- 推理接口：`POST http://localhost:8000/v1/chat/completions`

---

## 4. 基准测试

使用 `benchmark_experiment.py` 对部署的模型进行风格迁移测试。

### 4.1 测试基线模型（不使用 LoRA）

```bash
cd training

python benchmark_experiment.py \
    --api-url http://localhost:8000 \
    --model-label base \
    --quick
```

### 4.2 测试 LoRA 微调模型

```bash
python benchmark_experiment.py \
    --api-url http://localhost:8000 \
    --model-label lora \
    --quick
```

**完整参数**：

```bash
python benchmark_experiment.py \
    --api-url http://localhost:8000 \      # 部署服务地址
    --model-id <model_id> \                # 模型 ID（不指定则自动使用第一个可用模型）
    --model-label base \                   # 模型标签（用于结果文件命名，如 base/lora）
    --test-file dataset/test.jsonl \       # 测试集文件（不指定则使用内置默认案例）
    --styles 搞笑 古风 \                   # 只测试指定风格（默认全部）
    --quick                                # 快速模式（仅测试前 2 个案例）
```

**输出**：`results/benchmark_{label}_{timestamp}.json`

> 注意：基线和 LoRA 模型需要分别部署、分别测试。先部署基线跑一次 `--model-label base`，再部署 LoRA 跑一次 `--model-label lora`。

---

## 5. 评估对比

使用 `judge_benchmark.py` 对基线和 LoRA 的测试结果进行多维度评估。

```bash
cd training

# 基础评估（自动指标 + 相似度指标，不调用 LLM）
python judge_benchmark.py \
    --base results/benchmark_base_20260613_152504.json \
    --lora results/benchmark_lora_20260613_164216.json

# 包含 LLM 评判（调用 DeepSeek API 评估语义相似度）
python judge_benchmark.py \
    --base results/benchmark_base_20260613_152504.json \
    --lora results/benchmark_lora_20260613_164216.json \
    --judge-api-key sk-xxxx

# 只评估特定风格
python judge_benchmark.py \
    --base results/benchmark_base_20260613_152504.json \
    --lora results/benchmark_lora_20260613_164216.json \
    --styles 搞笑 古风

# 指定 LLM 评判的用例数
python judge_benchmark.py \
    --base results/benchmark_base_20260613_152504.json \
    --lora results/benchmark_lora_20260613_164216.json \
    --judge-api-key sk-xxxx \
    --max-cases 20
```

**评估维度**：

| 维度 | 说明 |
|------|------|
| 自动指标 | 空输出率、平均延迟、平均输出长度 |
| 相似度指标 | ROUGE-L、BLEU-4、长度比（output vs reference） |
| LLM 评判 | 语义相似度、风格匹配度、表达质量（1-5 分） |

**输出**：`results/judge_report_{timestamp}.json`

---

## 完整流程示例

```bash
# 1. 准备数据
cd training
python prepare_dataset.py --style all

# 2. 训练模型（三种风格）
bash scripts/train_gaoxiao.sh
bash scripts/train_gufeng.sh
bash scripts/train_yanqing.sh

# 3. 部署基线模型并测试
#    （修改 deploy_vllm.sh 不加载 LoRA，或直接用 vLLM 部署原始模型）
swift deploy --model Qwen/Qwen3-8B --host 0.0.0.0 --port 8000
python benchmark_experiment.py --model-label base

# 4. 部署 LoRA 模型并测试
bash scripts/deploy_vllm.sh
python benchmark_experiment.py --model-label lora

# 5. 评估对比
python judge_benchmark.py \
    --base results/benchmark_base_XXXXXXXX_XXXXXX.json \
    --lora results/benchmark_lora_XXXXXXXX_XXXXXX.json \
    --judge-api-key sk-xxxx
```
