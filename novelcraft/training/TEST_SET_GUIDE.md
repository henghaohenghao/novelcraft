# 测试集准备指南

## 问题：测试集哪来的？

当前测试集来源有两种方式：

### 方式一：从训练数据中分离（推荐）✅

使用 `prepare_test_set.py` 从现有训练数据中分离出独立的测试集。

**优点：**
- 测试集和训练集严格分离，避免数据泄露
- 测试样本来自真实数据分布
- 包含参考答案（目标风格文本）

**使用方法：**

```bash
# 从训练集中分离 10% 作为测试集
python prepare_test_set.py --test-ratio 0.1

# 指定用于 benchmark 的样本数（每个风格）
python prepare_test_set.py --benchmark-samples 10
```

**生成的文件结构：**
```
dataset/
├── gaoxiao_train_split.jsonl    # 新训练集（已移除测试样本）
├── gufeng_train_split.jsonl
├── yanqing_train_split.jsonl
├── test/                         # 完整测试集目录
│   ├── gaoxiao_test.jsonl
│   ├── gufeng_test.jsonl
│   └── yanqing_test.jsonl
└── benchmark/                    # 用于对比实验的精选样本
    └── test_cases.json
```

**test_cases.json 格式：**
```json
{
  "gaoxiao": [
    {
      "text": "原始通用风格文本",
      "reference": "目标风格参考答案"
    },
    ...
  ],
  "gufeng": [...],
  "yanqing": [...]
}
```

### 方式二：使用默认测试案例（快速测试）

如果没有准备测试集，`benchmark_experiment.py` 会使用内置的 5 个通用测试样例。

**缺点：**
- 测试样本较少，统计不够可靠
- 没有参考答案，无法计算某些指标
- 可能与训练数据重复

## 完整工作流程

### 1. 生成训练数据

```bash
# 从小说原文生成风格迁移训练数据
python prepare_dataset.py --style all
```

生成 `dataset/*_train.jsonl`

### 2. 分离测试集

```bash
# 分离 10% 作为测试集
python prepare_test_set.py --test-ratio 0.1 --benchmark-samples 10
```

生成：
- `*_train_split.jsonl`（新训练集）
- `test/*_test.jsonl`（完整测试集）
- `benchmark/test_cases.json`（对比实验用）

### 3. 训练模型

```bash
# 使用分离后的训练集进行训练
python train_style_lora.py \
  --style gaoxiao \
  --dataset dataset/gaoxiao_train_split.jsonl \
  --output-dir output
```

### 4. 运行对比实验

```bash
# 使用准备好的测试集
python benchmark_experiment.py --test-file dataset/benchmark/test_cases.json

# 快速测试
python benchmark_experiment.py --quick
```

### 5. 评估和可视化

```bash
# 计算评估指标
python metrics.py results/benchmark_*.json

# 生成可视化报告
python visualize_results.py \
  results/evaluation_*.json \
  --benchmark results/benchmark_*.json \
  --output results/report.html
```

## 测试集数量建议

| 数据集规模 | 测试集比例 | 最小样本数 | Benchmark 样本数 |
|-----------|-----------|-----------|-----------------|
| < 500 样本 | 20% | 50 | 10 |
| 500-2000 | 15% | 100 | 15 |
| 2000-5000 | 10% | 200 | 20 |
| > 5000 | 5% | 250 | 30 |

## 测试集质量保证

### 随机采样
使用固定随机种子确保可复现：
```bash
python prepare_test_set.py --seed 42
```

### 多样性检查
测试集应覆盖多种场景：
- 不同长度的文本（短/中/长）
- 不同主题（武侠/言情/日常）
- 不同难度（简单/复杂句式）

### 避免数据泄露
- ✅ 先分离测试集，再训练
- ✅ 测试集样本从未出现在训练数据中
- ❌ 不要用训练集样本进行评估

## FAQ

**Q: 已经训练完了，现在才准备测试集怎么办？**

A: 可以从 data/ 目录中的原始小说数据重新生成一批测试样本（确保不与训练集重复）：

```bash
# 使用不同的章节或小说生成测试集
python prepare_dataset.py \
  --input-file data/gaoxiao/另一本小说.jsonl \
  --style gaoxiao \
  --max-samples 50
```

**Q: 测试集需要人工标注吗？**

A: 不需要。我们的测试集是从训练数据分离出来的，已经包含了"通用风格→目标风格"的配对，可以直接使用。

**Q: 可以使用外部数据作为测试集吗？**

A: 可以，但需要准备成相同格式。对于没有参考答案的测试样本，某些指标（如 BLEU）无法计算，但仍可以评估风格匹配度。

**Q: 测试集太大，benchmark 实验太慢怎么办？**

A: 使用 `--benchmark-samples` 参数控制用于对比实验的样本数。完整测试集用于全面评估，benchmark 样本用于快速对比展示。

## 进阶：多轮评估

```bash
# 第一轮：快速对比（5个样本）
python benchmark_experiment.py --test-file dataset/benchmark/test_cases.json

# 第二轮：完整评估（所有测试集）
for style in gaoxiao gufeng yanqing; do
  python evaluate_full_test.py \
    --test-file dataset/test/${style}_test.jsonl \
    --style $style \
    --lora output/${style}-style-lora
done
```

## 总结

测试集来源的优先级：
1. **最佳**: 使用 `prepare_test_set.py` 从训练数据分离
2. **次优**: 使用额外的原始数据生成独立测试集
3. **快速测试**: 使用内置默认样例（不推荐用于正式评估）
