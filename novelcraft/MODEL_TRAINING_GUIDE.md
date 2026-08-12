# Qwen3-8B 风格迁移模型训练方案

## 目录

1. [训练目标](#训练目标)
2. [数据准备](#数据准备)
3. [训练环境](#训练环境)
4. [训练步骤](#训练步骤)
5. [模型部署](#模型部署)
6. [使用示例](#使用示例)

---

## 训练目标

使用 Qwen3-8B-Instruct 作为基座模型，通过 LoRA 微调训练多个风格适配器，实现文本风格转换功能。

**支持的风格**：
- 古龙（武侠小说）
- 曹文轩（儿童文学）
- 金庸（武侠小说）
- 刘慈欣（科幻小说）
- 王小波（当代文学）
- 鲁迅（现代文学）

---

## 数据准备

### 1. 数据收集

#### 方法一：从公开作品收集
```python
# 收集作家的公开作品
authors = {
    "gulong": ["多情剑客无情剑", "楚留香传奇", "陆小凤传奇"],
    "caowenxuan": ["草房子", "青铜葵花", "根鸟"],
    "jinyong": ["射雕英雄传", "天龙八部", "笑傲江湖"],
    # ... 其他作家
}

# 从网络文学平台、电子书等渠道收集文本
# 注意版权问题，仅用于研究和学习
```

#### 方法二：使用大模型生成训练数据
```python
# 使用 GPT-4 或其他大模型生成风格化数据
import openai

def generate_style_data(plain_text, style_name, style_description):
    """生成风格化训练数据"""
    prompt = f"""请将以下普通叙述文本改写为{style_name}的风格。

{style_name}的风格特点：
{style_description}

原文：
{plain_text}

改写后的文本："""
    
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    
    return response.choices[0].message.content
```

### 2. 数据格式

训练数据采用指令微调格式：

```json
{
  "instruction": "将以下文本转换为古龙的写作风格",
  "input": "夜色降临，一个黑衣人走进了客栈。他坐在角落里，默默地喝着酒。",
  "output": "夜。\n黑衣人来了。\n他坐在角落。\n一个人。\n一壶酒。\n沉默如铁。"
}
```

### 3. 数据集构建脚本

```python
# scripts/prepare_style_dataset.py
import json
from pathlib import Path

def create_training_sample(plain_text, styled_text, style_name):
    """创建单个训练样本"""
    return {
        "instruction": f"将以下文本转换为{style_name}的写作风格",
        "input": plain_text,
        "output": styled_text
    }

def build_dataset(style_name, text_pairs):
    """构建完整数据集"""
    dataset = []
    for plain, styled in text_pairs:
        sample = create_training_sample(plain, styled, style_name)
        dataset.append(sample)
    return dataset

# 示例：古龙风格数据
gulong_pairs = [
    (
        "夜色降临，一个黑衣人走进了客栈。他坐在角落里，默默地喝着酒。",
        "夜。\n黑衣人来了。\n他坐在角落。\n一个人。\n一壶酒。\n沉默如铁。"
    ),
    (
        "他拔出了剑，剑光闪烁，非常锋利。",
        "剑出鞘。\n寒光一闪。\n快如闪电。"
    ),
    # ... 更多样本
]

# 构建数据集
gulong_dataset = build_dataset("古龙", gulong_pairs)

# 保存为 JSON
output_path = Path("data/style_transfer/gulong_train.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(gulong_dataset, f, ensure_ascii=False, indent=2)

print(f"数据集已保存到 {output_path}")
print(f"样本数量: {len(gulong_dataset)}")
```

### 4. 数据集规模建议

| 风格 | 最少样本数 | 推荐样本数 | 说明 |
|------|-----------|-----------|------|
| 古龙 | 500 | 2000+ | 短句风格，需要更多样本 |
| 曹文轩 | 300 | 1500+ | 诗意化语言 |
| 金庸 | 500 | 2000+ | 复杂叙事 |
| 刘慈欣 | 300 | 1500+ | 科幻设定 |
| 王小波 | 300 | 1500+ | 幽默讽刺 |
| 鲁迅 | 300 | 1500+ | 批判现实 |

---

## 训练环境

### 硬件要求

- **GPU**: NVIDIA A100 (40GB) 或 RTX 4090 (24GB)
- **内存**: 32GB+
- **存储**: 100GB+ SSD

### 软件环境

```bash
# Python 环境
Python 3.10+

# 核心依赖
torch>=2.0.0
transformers>=4.36.0
peft>=0.7.0
datasets>=2.14.0
accelerate>=0.24.0
bitsandbytes>=0.41.0  # 用于 QLoRA
```

### 安装依赖

```bash
# 创建虚拟环境
conda create -n style-transfer python=3.10
conda activate style-transfer

# 安装 PyTorch (CUDA 12.1)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 安装其他依赖
pip install transformers peft datasets accelerate bitsandbytes
pip install sentencepiece protobuf
```

---

## 训练步骤

### 方法一：使用 LLaMA Factory（推荐）

LLaMA Factory 是一个易用的 LLM 微调框架，支持 Qwen 系列模型。

#### 1. 安装 LLaMA Factory

```bash
git clone https://github.com/hiyouga/LLaMA-Factory.git
cd LLaMA-Factory
pip install -e .
```

#### 2. 准备数据集配置

创建 `data/dataset_info.json`：

```json
{
  "gulong_style": {
    "file_name": "gulong_train.json",
    "formatting": "alpaca",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  },
  "caowenxuan_style": {
    "file_name": "caowenxuan_train.json",
    "formatting": "alpaca",
    "columns": {
      "prompt": "instruction",
      "query": "input",
      "response": "output"
    }
  }
}
```

#### 3. 训练配置

创建 `train_gulong.yaml`：

```yaml
### 模型配置
model_name_or_path: Qwen/Qwen3-8B-Instruct
quantization_bit: 4  # 使用 QLoRA 4-bit 量化

### LoRA 配置
lora_rank: 16
lora_alpha: 32
lora_dropout: 0.05
lora_target: all  # 对所有线性层应用 LoRA

### 训练配置
stage: sft
do_train: true
finetuning_type: lora
dataset: gulong_style
template: qwen
cutoff_len: 2048

### 训练参数
output_dir: outputs/gulong-style-lora
overwrite_output_dir: true
per_device_train_batch_size: 4
gradient_accumulation_steps: 4
learning_rate: 5.0e-5
num_train_epochs: 3
lr_scheduler_type: cosine
warmup_ratio: 0.1
logging_steps: 10
save_steps: 500
save_total_limit: 3

### 优化器
optim: adamw_torch
weight_decay: 0.01
max_grad_norm: 1.0

### 其他
fp16: true
report_to: tensorboard
```

#### 4. 启动训练

```bash
# 单卡训练
llamafactory-cli train train_gulong.yaml

# 多卡训练
CUDA_VISIBLE_DEVICES=0,1,2,3 llamafactory-cli train train_gulong.yaml
```

#### 5. 监控训练

```bash
# 启动 TensorBoard
tensorboard --logdir outputs/gulong-style-lora
```

### 方法二：使用原生 Transformers + PEFT

#### 训练脚本

```python
# scripts/train_style_lora.py
import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import load_dataset

# 1. 加载模型和分词器
model_name = "Qwen/Qwen3-8B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float16,
    device_map="auto",
    trust_remote_code=True
)

# 2. 配置 LoRA
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=16,  # LoRA 秩
    lora_alpha=32,
    lora_dropout=0.05,
    target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],  # Qwen3 的注意力层
    bias="none",
)

# 应用 LoRA
model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# 3. 加载数据集
dataset = load_dataset("json", data_files="data/style_transfer/gulong_train.json")

# 4. 数据预处理
def preprocess_function(examples):
    """将数据转换为模型输入格式"""
    inputs = []
    for instruction, input_text, output in zip(
        examples["instruction"],
        examples["input"],
        examples["output"]
    ):
        # 构建 Qwen3 的对话格式
        messages = [
            {"role": "system", "content": "你是一位专业的文学风格转换专家。"},
            {"role": "user", "content": f"{instruction}\n\n{input_text}"},
            {"role": "assistant", "content": output}
        ]
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=False
        )
        inputs.append(text)
    
    # 分词
    model_inputs = tokenizer(
        inputs,
        max_length=2048,
        truncation=True,
        padding=False
    )
    
    # 设置标签
    model_inputs["labels"] = model_inputs["input_ids"].copy()
    
    return model_inputs

# 处理数据集
tokenized_dataset = dataset.map(
    preprocess_function,
    batched=True,
    remove_columns=dataset["train"].column_names
)

# 5. 训练参数
training_args = TrainingArguments(
    output_dir="outputs/gulong-style-lora",
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=5e-5,
    num_train_epochs=3,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    logging_steps=10,
    save_steps=500,
    save_total_limit=3,
    fp16=True,
    report_to="tensorboard",
)

# 6. 数据整理器
data_collator = DataCollatorForSeq2Seq(
    tokenizer=tokenizer,
    model=model,
    padding=True
)

# 7. 训练器
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset["train"],
    data_collator=data_collator,
)

# 8. 开始训练
trainer.train()

# 9. 保存模型
trainer.save_model("outputs/gulong-style-lora/final")
tokenizer.save_pretrained("outputs/gulong-style-lora/final")
```

#### 运行训练

```bash
python scripts/train_style_lora.py
```

---

## 模型部署

### 使用 vLLM 部署

vLLM 是一个高性能的 LLM 推理引擎，支持 LoRA 适配器动态加载。

#### 1. 安装 vLLM

```bash
pip install vllm
```

#### 2. 启动 vLLM 服务

```bash
# 启动基座模型
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen3-8B-Instruct \
    --enable-lora \
    --lora-modules \
        gulong-style-lora=outputs/gulong-style-lora/final \
        caowenxuan-style-lora=outputs/caowenxuan-style-lora/final \
        jinyong-style-lora=outputs/jinyong-style-lora/final \
    --max-lora-rank 16 \
    --host 0.0.0.0 \
    --port 8000
```

#### 3. Docker 部署

创建 `Dockerfile.vllm`：

```dockerfile
FROM vllm/vllm-openai:latest

# 复制 LoRA 适配器
COPY outputs/gulong-style-lora/final /models/gulong-style-lora
COPY outputs/caowenxuan-style-lora/final /models/caowenxuan-style-lora
COPY outputs/jinyong-style-lora/final /models/jinyong-style-lora

# 启动脚本
CMD ["python", "-m", "vllm.entrypoints.openai.api_server", \
     "--model", "Qwen/Qwen3-8B-Instruct", \
     "--enable-lora", \
     "--lora-modules", \
     "gulong-style-lora=/models/gulong-style-lora", \
     "caowenxuan-style-lora=/models/caowenxuan-style-lora", \
     "jinyong-style-lora=/models/jinyong-style-lora", \
     "--max-lora-rank", "16", \
     "--host", "0.0.0.0", \
     "--port", "8000"]
```

构建和运行：

```bash
# 构建镜像
docker build -f Dockerfile.vllm -t novelcraft-vllm:latest .

# 运行容器
docker run --gpus all -p 8000:8000 novelcraft-vllm:latest
```

---

## 使用示例

### Python 客户端

```python
import httpx

async def transfer_style(text, style="gulong"):
    """调用风格迁移 API"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/v1/chat/completions",
            json={
                "model": "Qwen/Qwen3-8B-Instruct",
                "messages": [
                    {
                        "role": "system",
                        "content": "你是一位专业的文学风格转换专家。"
                    },
                    {
                        "role": "user",
                        "content": f"将以下文本转换为古龙的写作风格：\n\n{text}"
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 1000,
                "extra_body": {
                    "lora_adapter": f"{style}-style-lora"
                }
            }
        )
        result = response.json()
        return result["choices"][0]["message"]["content"]

# 使用示例
original = "夜色降临，一个黑衣人走进了客栈。他坐在角落里，默默地喝着酒。"
transformed = await transfer_style(original, style="gulong")
print(f"原文: {original}")
print(f"转换后: {transformed}")
```

### cURL 测试

```bash
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-8B-Instruct",
    "messages": [
      {
        "role": "system",
        "content": "你是一位专业的文学风格转换专家。"
      },
      {
        "role": "user",
        "content": "将以下文本转换为古龙的写作风格：\n\n夜色降临，一个黑衣人走进了客栈。"
      }
    ],
    "temperature": 0.7,
    "max_tokens": 1000,
    "extra_body": {
      "lora_adapter": "gulong-style-lora"
    }
  }'
```

---

## 训练技巧和优化

### 1. 数据质量优化

- **多样性**: 确保训练数据覆盖不同场景、情感、叙事角度
- **质量控制**: 人工审核生成的数据，去除低质量样本
- **平衡性**: 各类型样本数量相对均衡

### 2. 超参数调优

```python
# 推荐的超参数范围
hyperparameters = {
    "lora_rank": [8, 16, 32],  # 秩越大，表达能力越强，但训练成本越高
    "lora_alpha": [16, 32, 64],  # 通常设为 rank 的 2 倍
    "learning_rate": [1e-5, 5e-5, 1e-4],
    "batch_size": [4, 8, 16],
    "epochs": [3, 5, 10],
}
```

### 3. 评估指标

```python
# 评估脚本
def evaluate_style_transfer(model, test_dataset):
    """评估风格迁移质量"""
    metrics = {
        "perplexity": [],  # 困惑度
        "bleu": [],  # BLEU 分数
        "style_similarity": [],  # 风格相似度
    }
    
    for sample in test_dataset:
        # 生成转换文本
        generated = model.generate(sample["input"])
        
        # 计算指标
        metrics["perplexity"].append(calculate_perplexity(generated))
        metrics["bleu"].append(calculate_bleu(generated, sample["output"]))
        metrics["style_similarity"].append(
            calculate_style_similarity(generated, sample["style"])
        )
    
    return {k: sum(v) / len(v) for k, v in metrics.items()}
```

### 4. 常见问题

**问题 1: 过拟合**
- 解决方案: 增加数据量、使用 dropout、early stopping

**问题 2: 风格不明显**
- 解决方案: 增加训练轮数、提高 LoRA rank、优化训练数据

**问题 3: 生成质量不稳定**
- 解决方案: 调整 temperature、top_p 参数

---

## 附录

### A. 完整训练脚本

见 `scripts/train_all_styles.sh`

### B. 数据集示例

见 `data/style_transfer/examples/`

### C. 评估工具

见 `scripts/evaluate_style.py`

### D. 参考资源

- [Qwen3 官方文档](https://github.com/QwenLM/Qwen)
- [LLaMA Factory](https://github.com/hiyouga/LLaMA-Factory)
- [vLLM 文档](https://docs.vllm.ai/)
- [PEFT 文档](https://huggingface.co/docs/peft)

---

**训练完成后，将 LoRA 适配器部署到 vLLM，即可通过 NovelCraft 后端 API 调用！**
