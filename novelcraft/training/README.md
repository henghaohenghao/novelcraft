# 风格迁移模型训练方案

使用 ms-swift 训练 Qwen3-8B 的 LoRA 适配器，实现不同作家风格的文本转换。

## 环境准备

```bash
# 创建虚拟环境
conda create -n novelcraft-train python=3.10
conda activate novelcraft-train

# 安装依赖
pip install -r requirements-training.txt
```

## 数据集准备

### 1. 数据格式

ms-swift 支持的对话格式（jsonl）:
```json
{"messages": [
  {"role": "system", "content": "你是一位专业的文学风格转换专家..."},
  {"role": "user", "content": "请将以下文本转换为古龙的写作风格：\n\n原始文本"},
  {"role": "assistant", "content": "转换后的文本"}
]}
```

### 2. 数据来源建议

- **原著小说**: 从公开资源获取各作家的代表作品
- **句对生成**: 使用大模型生成"通用风格→目标风格"的对照数据
- **数据增强**: 通过改写、回译等方式扩充数据集

### 3. 数据规模建议

- 每个风格：1000-5000 条训练样本
- 验证集：10-20% 的数据

## 训练流程

### 方式一：使用 ms-swift CLI（推荐）

```bash
# 训练古龙风格 LoRA
swift sft \
  --model_type qwen3-8b-instruct \
  --dataset dataset/gulong_train.jsonl \
  --num_train_epochs 3 \
  --lora_rank 8 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --lora_target_modules ALL \
  --gradient_checkpointing true \
  --batch_size 4 \
  --gradient_accumulation_steps 4 \
  --learning_rate 1e-4 \
  --warmup_ratio 0.05 \
  --save_strategy epoch \
  --output_dir output/gulong-style-lora \
  --bf16 true \
  --logging_steps 10
```

### 方式二：使用 Python 脚本

见 `train_style_lora.py`

## LoRA 参数建议

- **rank**: 8-16（8 适合快速实验，16 效果更好）
- **alpha**: rank * 2 ~ rank * 4
- **dropout**: 0.05-0.1
- **target_modules**: 全部线性层（ALL）或 q_proj,k_proj,v_proj,o_proj,up_proj,down_proj

## 与 vLLM 集成

训练完成后，vLLM 支持动态加载 LoRA:

```bash
# 启动 vLLM 服务（支持 LoRA）
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-8B-Instruct \
  --enable-lora \
  --lora-modules gulong-style-lora=./output/gulong-style-lora \
  --lora-modules caowenxuan-style-lora=./output/caowenxuan-style-lora \
  --max-lora-rank 16
```

请求时指定 LoRA:
```json
{
  "model": "Qwen/Qwen3-8B-Instruct",
  "messages": [...],
  "extra_body": {
    "lora_adapter": "gulong-style-lora"
  }
}
```

## 质量评估

1. **自动评估**: BLEU、ROUGE、困惑度
2. **人工评估**: 风格一致性、内容保真度、流畅度
3. **A/B 测试**: 对比不同 LoRA 版本

## 训练优化技巧

1. **多阶段训练**: 先用大 lr 训练，再用小 lr 微调
2. **数据清洗**: 过滤低质量样本
3. **混合训练**: 多个风格一起训练，用 prefix 区分
4. **定期验证**: 每个 epoch 生成样例检查效果
