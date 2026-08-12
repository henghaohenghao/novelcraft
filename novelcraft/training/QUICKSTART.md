# 快速开始指南

使用 ms-swift 训练 Qwen3-8B 风格迁移 LoRA 的完整流程。

## 🚀 快速开始

### 1. 环境准备（5分钟）

```bash
# 创建虚拟环境
conda create -n novelcraft-train python=3.10
conda activate novelcraft-train

# 安装依赖
cd novelcraft/training
pip install -r requirements-training.txt
```

### 2. 数据准备（最关键）

#### 方式 A：创建示例数据集（快速测试）

```bash
python prepare_dataset.py --action example
```

这会创建一个小型的古龙风格示例数据集，可用于测试流程。

#### 方式 B：准备真实数据集（推荐）

创建 `dataset/{style}_train.jsonl` 文件，格式如下：

```json
{"messages": [
  {"role": "system", "content": "你是一位专业的文学风格转换专家..."},
  {"role": "user", "content": "请将以下文本转换为古龙的写作风格：\n\n原始文本"},
  {"role": "assistant", "content": "转换后的古龙风格文本"}
]}
```

**数据获取建议**：
- 从公开小说语料中提取段落
- 使用 GPT-4 等大模型生成"通用→目标风格"的数据对
- 人工标注少量高质量样本作为种子数据

**数据规模**：
- 快速实验：100-500 条
- 生产使用：1000-5000 条
- 每个风格独立准备一个数据集

### 3. 训练 LoRA

#### 单个风格训练

```bash
# 训练古龙风格
python train_style_lora.py \
  --style gulong \
  --dataset dataset/gulong_train.jsonl \
  --epochs 3 \
  --lora-rank 8
```

#### 批量训练所有风格

```bash
python train_style_lora.py --all
```

或使用一键脚本：

```bash
bash train_all.sh
```

#### 使用命令行直接训练（不用脚本）

```bash
swift sft \
  --model_type qwen3-8b-instruct \
  --dataset dataset/gulong_train.jsonl \
  --num_train_epochs 3 \
  --lora_rank 8 \
  --lora_alpha 32 \
  --lora_target_modules ALL \
  --batch_size 4 \
  --gradient_accumulation_steps 4 \
  --learning_rate 1e-4 \
  --output_dir output/gulong-style-lora \
  --bf16 true \
  --gradient_checkpointing true
```

### 4. 部署到 vLLM

训练完成后，启动带 LoRA 的 vLLM 服务：

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-8B-Instruct \
  --enable-lora \
  --lora-modules gulong-style-lora=./output/gulong-style-lora \
  --lora-modules caowenxuan-style-lora=./output/caowenxuan-style-lora \
  --max-lora-rank 16
```

### 5. 测试效果

```bash
# 测试单个风格
python test_lora.py \
  --style 古龙 \
  --lora gulong-style-lora \
  --text "夜色渐深，街道上空无一人。"

# 对比所有风格
python test_lora.py --compare --text "夜色渐深，街道上空无一人。"

# 对比基线模型和 LoRA
python test_lora.py --baseline --style 古龙 --lora gulong-style-lora
```

## 📊 训练参数调优

### LoRA 参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| rank | 8-16 | 8 快速实验，16 更好效果 |
| alpha | 32 | 通常是 rank × 4 |
| dropout | 0.05 | 防止过拟合 |
| target_modules | ALL | 全部线性层 |

### 训练参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| epochs | 3-5 | 观察验证集损失 |
| batch_size | 4 | 根据显存调整 |
| learning_rate | 1e-4 | LoRA 标准学习率 |
| warmup_ratio | 0.05 | 前 5% 步数预热 |

### 显存优化

如果显存不足，尝试：
1. 减小 `batch_size`（但保持 `batch_size × gradient_accumulation_steps` 不变）
2. 开启 `gradient_checkpointing`
3. 减小 `max_length`
4. 使用 `int8` 量化训练

```bash
swift sft \
  --model_type qwen3-8b-instruct \
  --quantization_bit 8 \  # 8-bit 量化
  ...
```

## 🔍 效果评估

### 自动评估指标

训练脚本会自动计算：
- **Loss**: 训练损失和验证损失
- **Perplexity**: 困惑度（越低越好）

### 人工评估维度

1. **风格一致性**：是否体现目标作家的语言特点？
2. **内容保真度**：是否保留原文的核心内容？
3. **流畅度**：转换后的文本是否自然流畅？
4. **创造性**：是否有符合风格的创新表达？

### A/B 测试

```python
# 使用 test_lora.py 进行对比
python test_lora.py --baseline --compare
```

## 🐛 常见问题

### 1. CUDA Out of Memory

**解决方案**：
```bash
# 减小批次大小
--batch_size 2 --gradient_accumulation_steps 8

# 或使用量化
--quantization_bit 8
```

### 2. 训练损失不下降

**可能原因**：
- 学习率过大或过小
- 数据质量问题
- LoRA rank 太小

**解决方案**：
- 调整学习率：`1e-5` 到 `5e-4`
- 检查数据集格式和质量
- 增加 LoRA rank 到 16

### 3. 生成效果不理想

**可能原因**：
- 训练数据不足或质量低
- 过拟合或欠拟合
- Prompt 设计不当

**解决方案**：
- 增加训练数据（至少 500 条）
- 调整训练轮数
- 优化 system prompt

### 4. vLLM 无法加载 LoRA

**检查**：
- LoRA 目录是否包含 `adapter_config.json` 和 `adapter_model.safetensors`
- `--max-lora-rank` 是否 >= 实际 rank
- vLLM 版本是否支持 LoRA（需要 >= 0.3.0）

## 📈 进阶技巧

### 1. 多阶段训练

```bash
# 第一阶段：大学习率
swift sft --learning_rate 5e-4 --num_train_epochs 2 ...

# 第二阶段：小学习率微调
swift sft --learning_rate 1e-5 --num_train_epochs 1 \
  --resume_from_checkpoint output/gulong-style-lora/checkpoint-xxx
```

### 2. 数据增强

使用大模型生成更多训练数据：

```python
# 见 prepare_dataset.py 中的 generate_synthetic_data_with_llm
python prepare_dataset.py --action generate --style gulong
```

### 3. 混合风格训练

在 prompt 中加入风格标识，用一个 LoRA 支持多个风格：

```json
{"role": "user", "content": "[STYLE:古龙] 请转换：原文"}
```

## 📚 参考资料

- [ms-swift 文档](https://github.com/modelscope/swift)
- [Qwen3 模型卡](https://huggingface.co/Qwen/Qwen3-8B-Instruct)
- [LoRA 论文](https://arxiv.org/abs/2106.09685)
- [vLLM LoRA 支持](https://docs.vllm.ai/en/latest/models/lora.html)

## 💡 最佳实践总结

1. **数据质量 > 数据数量**：500 条高质量数据胜过 5000 条低质量数据
2. **先小规模实验**：用 100 条数据快速验证流程
3. **监控验证集损失**：防止过拟合
4. **人工评估很重要**：自动指标不能完全反映风格质量
5. **迭代优化**：根据测试结果不断调整数据和参数
