# 风格迁移微调效果对比实验

完整的实验设计方案，通过对比基线模型和微调模型，量化展示 LoRA 微调的效果提升。

## 实验设计

### 对比维度

1. **基线模型（Baseline）**: Qwen3-8B-Instruct 原始模型
2. **微调模型（Fine-tuned）**: 基线模型 + 风格 LoRA 适配器

### 评估指标

| 指标类别 | 具体指标 | 说明 |
|---------|---------|------|
| **内容保真度** | BLEU-2, BLEU-3 | 与原文的 n-gram 重叠度 |
| | ROUGE-L | 最长公共子序列匹配 |
| | 编辑距离 | 字符级差异 |
| **风格匹配度** | 风格关键词得分 | 特定风格词汇出现频率 |
| | 词汇丰富度 | 类型-标记比（TTR） |
| **生成质量** | 长度比例 | 生成文本与原文长度对比 |
| | 生成延迟 | 推理速度对比 |

### 测试案例

5 个不同场景的测试文本：
- 武侠场景（适合古龙、金庸风格）
- 情感场景（适合曹文轩风格）
- 日常场景
- 悬疑场景
- 风景描写

## 使用步骤

### 1. 启动 vLLM 服务（带 LoRA 支持）

```bash
python -m vllm.entrypoints.openai.api_server \
  --model Qwen/Qwen3-8B-Instruct \
  --enable-lora \
  --lora-modules gulong-style-lora=./output/gulong-style-lora \
  --lora-modules jinyong-style-lora=./output/jinyong-style-lora \
  --lora-modules caowenxuan-style-lora=./output/caowenxuan-style-lora \
  --max-lora-rank 16 \
  --port 8000
```

### 2. 运行对比实验

```bash
# 完整实验（所有风格 + 所有测试案例）
python benchmark_experiment.py

# 快速测试（前 2 个案例）
python benchmark_experiment.py --quick
```

输出示例：
```
======================================================================
风格迁移对比实验
======================================================================
测试案例数: 5
测试风格数: 3
总测试次数: 30 (基线 + 微调)

======================================================================
对比实验: 古龙
======================================================================

测试案例 1/5
原文: 夜色渐深，街道上的行人越来越少...
  [1/2] 基线模型生成中...
  [2/2] 微调模型生成中...
  ✓ 完成 (基线: 2.34s, 微调: 2.41s)

...

✓ 结果已保存到: results/benchmark_20260611_143052.json
```

### 3. 计算评估指标

```bash
python metrics.py results/benchmark_20260611_143052.json
```

输出示例：
```
======================================================================
评估结果摘要
======================================================================

总体统计:
  测试风格数: 3
  测试案例数: 15

平均改进率:
  style_score         : +45.23% (±12.34%)
  bleu_2              : +18.76% (±8.91%)
  rouge_l             : +22.45% (±10.12%)

各风格详细结果:

  古龙:
    风格匹配分数改进: +52.30%
    BLEU-2 改进:      +20.15%
    ROUGE-L 改进:     +25.67%
```

### 4. 生成可视化报告

```bash
python visualize_results.py \
  results/evaluation_benchmark_20260611_143052.json \
  --benchmark results/benchmark_20260611_143052.json \
  --output results/report.html \
  --markdown
```

生成两种格式的报告：
- **HTML 报告**: 交互式网页，包含表格、样例对比
- **Markdown 报告**: 纯文本格式，方便分享

## 预期效果展示

### 量化指标对比

| 指标 | 基线模型 | 微调模型 | 改进幅度 |
|------|---------|---------|---------|
| 风格匹配分数 | 0.15 | 0.68 | **+353%** |
| BLEU-2 | 0.42 | 0.51 | **+21%** |
| ROUGE-L | 0.38 | 0.47 | **+24%** |
| 词汇丰富度 | 0.72 | 0.78 | **+8%** |

### 质性对比示例

**原文**:
> 夜色渐深，街道上的行人越来越少，只剩下远处几盏昏黄的灯光在风中摇曳。

**基线模型输出**（通用风格）:
> 随着夜幕降临，街道上的人流逐渐稀疏，只有远处的几盏路灯在夜风中轻轻摇晃，发出微弱的光芒。

**微调模型输出**（古龙风格）:
> 夜，越来越深。街上的人，越来越少。只剩下几盏昏黄的灯，在风中摇晃。灯光很暗，夜色很浓。

**效果分析**:
- ✅ 短句式、断句风格明显
- ✅ 营造悬疑感、节奏感
- ✅ 风格关键词增多（"深"、"暗"、"浓"）
- ✅ 保持原文核心内容

## 实验变量控制

### 控制变量
- 相同的基础模型（Qwen3-8B-Instruct）
- 相同的推理参数（temperature=0.7, top_p=0.9）
- 相同的系统提示词
- 相同的测试案例

### 唯一变量
- 是否加载 LoRA 适配器

## 统计显著性

为确保结果可信：
- 每个风格测试 5 个不同案例
- 计算均值和标准差
- 多风格交叉验证

## 结果解读

### 风格匹配分数大幅提升 (+353%)
说明微调模型能更准确地学习和应用目标风格特征。

### BLEU/ROUGE 适度提升 (+20%)
保持了内容保真度，在风格转换的同时不偏离原文语义。

### 词汇丰富度提升 (+8%)
微调模型使用更多样化的词汇，文学性更强。

## 扩展实验

### A. 人工评估
```bash
# 生成评估样本
python generate_eval_samples.py results/benchmark_*.json \
  --output eval_samples.json

# 人工打分（风格一致性、流畅度、内容保真度）
# 使用 eval_samples.json 进行盲测评估
```

### B. 不同 LoRA rank 对比
```bash
# 训练不同 rank 的模型
python train_style_lora.py --lora-rank 4 --output-dir output/rank4
python train_style_lora.py --lora-rank 8 --output-dir output/rank8
python train_style_lora.py --lora-rank 16 --output-dir output/rank16

# 运行对比实验
python benchmark_experiment.py --compare-ranks
```

### C. 数据量影响分析
测试不同训练样本数量（500/1000/2000/5000）对效果的影响。

## 论文/报告写作建议

### 实验章节结构
1. **实验设计**: 对比维度、评估指标、测试案例
2. **实验设置**: 模型配置、训练参数、推理参数
3. **实验结果**: 量化指标表格、统计分析
4. **案例分析**: 典型样例对比、质性分析
5. **消融实验**: rank、数据量、训练轮数影响

### 图表建议
- 📊 柱状图: 各指标基线 vs 微调对比
- 📈 折线图: 不同 rank 的效果曲线
- 📝 表格: 详细指标数据 + 标准差
- 💬 文本框: 并排展示生成样例

## 常见问题

**Q: 为什么风格分数提升大，但 BLEU 提升小？**  
A: 风格迁移不是翻译任务，BLEU 主要衡量与原文的相似度。风格转换需要改变表达方式，所以 BLEU 不应过高。

**Q: 如何解释负向改进？**  
A: 某些指标可能出现负向改进（如编辑距离增大），这通常是风格化的副作用。需要综合多个指标判断。

**Q: 如何确定实验有效？**  
A: 关注风格匹配分数和人工评估。量化指标只是参考，最终还需人工验证风格转换质量。

## 文件说明

| 文件 | 说明 |
|------|------|
| `benchmark_experiment.py` | 主实验脚本，运行基线 vs 微调对比 |
| `metrics.py` | 评估指标计算（BLEU, ROUGE, 风格分数等） |
| `visualize_results.py` | 生成 HTML/Markdown 可视化报告 |
| `results/benchmark_*.json` | 实验原始数据（生成文本 + 元数据） |
| `results/evaluation_*.json` | 评估指标数据 |
| `results/report.html` | 可视化对比报告 |

## 引用建议

如在学术论文中使用此实验方案，建议引用：
- **LoRA**: Hu et al. "LoRA: Low-Rank Adaptation of Large Language Models" (ICLR 2022)
- **BLEU**: Papineni et al. "BLEU: a Method for Automatic Evaluation of Machine Translation" (ACL 2002)
- **ROUGE**: Lin "ROUGE: A Package for Automatic Evaluation of Summaries" (2004)
