# 风格迁移训练方案总结

## 📋 完整方案概览

使用 **ms-swift** 训练 **Qwen3-8B** 模型的 LoRA 适配器，实现 6 种作家风格的文本转换。

## 🎯 技术架构

```
基础模型: Qwen3-8B-Instruct (8B 参数)
    ↓
训练方法: LoRA (Low-Rank Adaptation)
    ↓
训练框架: ms-swift (ModelScope Swift)
    ↓
部署方式: vLLM (动态加载 LoRA)
    ↓
后端集成: FastAPI (已有代码 style_transfer_service.py)
```

## 📂 项目结构

```
novelcraft/training/
├── README.md                    # 总体说明
├── QUICKSTART.md               # 快速开始指南（⭐ 从这里开始）
├── requirements-training.txt   # 训练环境依赖
├── config.example.yaml         # 配置示例
├── train_style_lora.py         # 训练脚本（核心）
├── prepare_dataset.py          # 数据准备工具
├── test_lora.py               # 测试脚本
├── train_all.sh               # 一键训练脚本
├── dataset/                    # 训练数据（需自行准备）
│   ├── gulong_train.jsonl
│   ├── caowenxuan_train.jsonl
│   └── ...
└── output/                     # 训练输出
    ├── gulong-style-lora/
    ├── caowenxuan-style-lora/
    └── ...
```

## 🚀 核心流程（4 步）

### 1️⃣ 环境准备
```bash
conda create -n novelcraft-train python=3.10
conda activate novelcraft-train
pip install -r requirements-training.txt
```

### 2️⃣ 数据准备（最关键）
- 格式：jsonl，每行一个训练样本
- 结构：system + user + assistant 三轮对话
- 规模：每个风格 1000-5000 条（最少 100 条用于测试）

**快速测试**：
```bash
python prepare_dataset.py --action example  # 生成示例数据集
```

**生产使用**：需要准备真实的"原文→目标风格"数据对

### 3️⃣ 训练 LoRA
```bash
# 单风格训练
python train_style_lora.py --style gulong --dataset dataset/gulong_train.jsonl

# 批量训练所有风格
python train_style_lora.py --all
```

### 4️⃣ 部署集成
```bash
# 启动 vLLM（支持 LoRA）
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-8B-Instruct \
  --enable-lora \
  --lora-modules gulong-style-lora=./output/gulong-style-lora \
  --max-lora-rank 16
```

你的 FastAPI 后端会自动通过 `extra_body` 参数调用对应的 LoRA。

## ⚙️ 关键参数

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| **LoRA rank** | 8-16 | 平衡效果和速度 |
| **LoRA alpha** | 32 | rank × 4 |
| **学习率** | 1e-4 | LoRA 标准值 |
| **训练轮数** | 3-5 | 观察验证集损失 |
| **批次大小** | 4 | 根据显存调整 |

## 💡 数据准备建议

### 方法 1：从原著提取（质量最高）
- 下载各作家的小说 txt
- 切分成段落
- 使用 GPT-4 生成"通用风格→目标风格"的对照

### 方法 2：使用大模型生成
```python
# 见 prepare_dataset.py 的 generate_synthetic_data_with_llm
```

### 方法 3：人工标注
- 少量高质量样本（50-100 条）
- 作为种子数据

### 数据质量检查清单
- ✅ 风格特征明显
- ✅ 内容对应准确
- ✅ 长度适中（50-500 字）
- ✅ 格式正确（jsonl）

## 🧪 测试验证

```bash
# 单风格测试
python test_lora.py --style 古龙 --lora gulong-style-lora

# 多风格对比
python test_lora.py --compare

# 对比基线模型
python test_lora.py --baseline
```

## 🔧 常见问题速查

| 问题 | 解决方案 |
|------|----------|
| **显存不足** | 减小 batch_size，开启 gradient_checkpointing |
| **训练不收敛** | 调整学习率，检查数据质量 |
| **效果不理想** | 增加数据量，调整 LoRA rank |
| **vLLM 加载失败** | 检查 adapter_config.json 是否存在 |

## 📊 预期效果

- **训练时间**：单风格 1-3 小时（1000 条数据，单卡 A100）
- **模型大小**：每个 LoRA 约 10-50 MB（相比基础模型的 16GB）
- **推理速度**：与基础模型基本相同
- **风格质量**：明显优于纯 prompt 工程

## 🎓 核心优势

1. **轻量级**：LoRA 只有几十 MB，不需要存储多个完整模型
2. **动态切换**：vLLM 支持一次加载多个 LoRA，请求时指定
3. **易于迭代**：训练快速，可以快速实验不同参数
4. **成本低**：相比全参数微调，显存和时间成本降低 90%

## 📚 相关文档

- **快速开始**：[QUICKSTART.md](QUICKSTART.md) ⭐
- **详细说明**：[README.md](README.md)
- **配置示例**：[config.example.yaml](config.example.yaml)

## 🎯 下一步行动

1. **阅读快速开始指南**：[QUICKSTART.md](QUICKSTART.md)
2. **准备一个风格的小数据集**（100 条）测试流程
3. **训练第一个 LoRA**
4. **测试效果并迭代**
5. **扩展到所有 6 个风格**

---

**提示**：数据质量是关键！建议先用 100 条高质量数据测试流程，验证可行后再扩展。
