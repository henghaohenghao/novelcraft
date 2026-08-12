"""
评估指标计算模块

支持多种评估指标：
1. BLEU - 机器翻译常用指标
2. ROUGE - 文本摘要常用指标
3. 字符级编辑距离
4. 长度对比
5. 词汇丰富度
"""
import json
from pathlib import Path
from typing import Dict, List
import statistics
from collections import Counter
import re


def calculate_bleu(reference: str, hypothesis: str, n: int = 2) -> float:
    """计算 BLEU 分数（简化版，基于字符 n-gram）

    Args:
        reference: 参考文本
        hypothesis: 生成文本
        n: n-gram 大小
    """
    if not reference or not hypothesis:
        return 0.0

    # 提取 n-grams
    def get_ngrams(text: str, n: int) -> List[str]:
        return [text[i:i+n] for i in range(len(text) - n + 1)]

    ref_ngrams = Counter(get_ngrams(reference, n))
    hyp_ngrams = Counter(get_ngrams(hypothesis, n))

    # 计算匹配数
    matches = sum((ref_ngrams & hyp_ngrams).values())
    total = sum(hyp_ngrams.values())

    if total == 0:
        return 0.0

    precision = matches / total

    # 长度惩罚
    bp = min(1.0, len(hypothesis) / max(len(reference), 1))

    return bp * precision


def calculate_rouge_l(reference: str, hypothesis: str) -> float:
    """计算 ROUGE-L 分数（基于最长公共子序列）"""

    def lcs_length(s1: str, s2: str) -> int:
        """计算最长公共子序列长度"""
        m, n = len(s1), len(s2)
        dp = [[0] * (n + 1) for _ in range(m + 1)]

        for i in range(1, m + 1):
            for j in range(1, n + 1):
                if s1[i-1] == s2[j-1]:
                    dp[i][j] = dp[i-1][j-1] + 1
                else:
                    dp[i][j] = max(dp[i-1][j], dp[i][j-1])

        return dp[m][n]

    if not reference or not hypothesis:
        return 0.0

    lcs_len = lcs_length(reference, hypothesis)

    recall = lcs_len / len(reference) if len(reference) > 0 else 0
    precision = lcs_len / len(hypothesis) if len(hypothesis) > 0 else 0

    if recall + precision == 0:
        return 0.0

    f1 = 2 * precision * recall / (precision + recall)
    return f1


def calculate_edit_distance(s1: str, s2: str) -> int:
    """计算编辑距离（Levenshtein 距离）"""
    m, n = len(s1), len(s2)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    for i in range(m + 1):
        dp[i][0] = i
    for j in range(n + 1):
        dp[0][j] = j

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i-1] == s2[j-1]:
                dp[i][j] = dp[i-1][j-1]
            else:
                dp[i][j] = min(dp[i-1][j], dp[i][j-1], dp[i-1][j-1]) + 1

    return dp[m][n]


def calculate_lexical_diversity(text: str) -> float:
    """计算词汇丰富度（类型-标记比）"""
    # 简单分词（基于标点和空格）
    tokens = re.findall(r'[\w]+', text)

    if len(tokens) == 0:
        return 0.0

    types = len(set(tokens))
    return types / len(tokens)


def calculate_style_score(text: str, style_keywords: List[str]) -> float:
    """计算风格匹配分数（基于关键词出现频率）

    Args:
        text: 生成文本
        style_keywords: 风格特征词列表
    """
    text_lower = text.lower()
    matches = sum(1 for keyword in style_keywords if keyword in text_lower)
    return matches / max(len(style_keywords), 1)


# 各风格的特征词（示例）
STYLE_KEYWORDS = {
    "古龙": ["剑", "血", "酒", "月", "影", "刀", "风", "雨", "江湖", "杀手", "决战"],
    "金庸": ["武功", "内力", "掌法", "剑法", "真气", "经脉", "侠客", "武林", "门派"],
    "曹文轩": ["阳光", "麦田", "河流", "童年", "记忆", "温暖", "纯真", "乡村"],
}


def evaluate_single_case(case: Dict, style: str) -> Dict:
    """评估单个测试案例"""

    original = case["original"]
    baseline_output = case["baseline"]["output"]
    finetuned_output = case["finetuned"]["output"]
    reference = case.get("reference", original)

    # 风格特征词
    style_keywords = STYLE_KEYWORDS.get(style, [])

    metrics = {
        "case_id": case["id"],

        # 基线模型指标
        "baseline": {
            "bleu_2": calculate_bleu(reference, baseline_output, n=2),
            "bleu_3": calculate_bleu(reference, baseline_output, n=3),
            "rouge_l": calculate_rouge_l(reference, baseline_output),
            "edit_distance": calculate_edit_distance(original, baseline_output),
            "length": len(baseline_output),
            "length_ratio": len(baseline_output) / max(len(original), 1),
            "lexical_diversity": calculate_lexical_diversity(baseline_output),
            "style_score": calculate_style_score(baseline_output, style_keywords),
        },

        # 微调模型指标
        "finetuned": {
            "bleu_2": calculate_bleu(reference, finetuned_output, n=2),
            "bleu_3": calculate_bleu(reference, finetuned_output, n=3),
            "rouge_l": calculate_rouge_l(reference, finetuned_output),
            "edit_distance": calculate_edit_distance(original, finetuned_output),
            "length": len(finetuned_output),
            "length_ratio": len(finetuned_output) / max(len(original), 1),
            "lexical_diversity": calculate_lexical_diversity(finetuned_output),
            "style_score": calculate_style_score(finetuned_output, style_keywords),
        },
    }

    # 计算改进百分比
    metrics["improvement"] = {}
    for metric_name in ["bleu_2", "bleu_3", "rouge_l", "lexical_diversity", "style_score"]:
        baseline_val = metrics["baseline"][metric_name]
        finetuned_val = metrics["finetuned"][metric_name]

        if baseline_val > 0:
            improvement = (finetuned_val - baseline_val) / baseline_val * 100
        else:
            improvement = 0.0

        metrics["improvement"][metric_name] = improvement

    return metrics


def evaluate_benchmark_results(results_file: str) -> Dict:
    """评估完整的基准测试结果"""

    with open(results_file, "r", encoding="utf-8") as f:
        benchmark_results = json.load(f)

    evaluation = {
        "styles": [],
        "overall_summary": {},
    }

    all_improvements = {
        "bleu_2": [],
        "bleu_3": [],
        "rouge_l": [],
        "lexical_diversity": [],
        "style_score": [],
    }

    for style_result in benchmark_results:
        style = style_result["style"]
        test_cases = style_result["test_cases"]

        print(f"\n评估风格: {style}")

        style_metrics = {
            "style": style,
            "lora_adapter": style_result["lora_adapter"],
            "cases": [],
            "aggregate": {},
        }

        # 评估每个案例
        for case in test_cases:
            case_metrics = evaluate_single_case(case, style)
            style_metrics["cases"].append(case_metrics)

        # 聚合统计
        for metric_type in ["baseline", "finetuned"]:
            style_metrics["aggregate"][metric_type] = {}

            for metric_name in ["bleu_2", "rouge_l", "lexical_diversity", "style_score"]:
                values = [c[metric_type][metric_name] for c in style_metrics["cases"]]
                style_metrics["aggregate"][metric_type][metric_name] = {
                    "mean": statistics.mean(values),
                    "std": statistics.stdev(values) if len(values) > 1 else 0.0,
                    "min": min(values),
                    "max": max(values),
                }

        # 聚合改进统计
        style_metrics["aggregate"]["improvement"] = {}
        for metric_name in ["bleu_2", "rouge_l", "style_score"]:
            improvements = [c["improvement"][metric_name] for c in style_metrics["cases"]]
            style_metrics["aggregate"]["improvement"][metric_name] = {
                "mean": statistics.mean(improvements),
                "std": statistics.stdev(improvements) if len(improvements) > 1 else 0.0,
            }

            # 收集到总体统计
            all_improvements[metric_name].extend(improvements)

        evaluation["styles"].append(style_metrics)

    # 总体统计
    evaluation["overall_summary"] = {
        "total_styles": len(benchmark_results),
        "total_cases": sum(len(s["test_cases"]) for s in benchmark_results),
        "average_improvement": {
            metric: {
                "mean": statistics.mean(values),
                "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            }
            for metric, values in all_improvements.items()
        }
    }

    return evaluation


def save_evaluation(evaluation: Dict, output_file: str):
    """保存评估结果"""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(evaluation, f, ensure_ascii=False, indent=2)

    print(f"\n✓ 评估结果已保存到: {output_path}")


def print_evaluation_summary(evaluation: Dict):
    """打印评估摘要"""

    print("\n" + "="*70)
    print("评估结果摘要")
    print("="*70)

    overall = evaluation["overall_summary"]
    print(f"\n总体统计:")
    print(f"  测试风格数: {overall['total_styles']}")
    print(f"  测试案例数: {overall['total_cases']}")

    print(f"\n平均改进率:")
    for metric, stats in overall["average_improvement"].items():
        print(f"  {metric:20s}: {stats['mean']:+.2f}% (±{stats['std']:.2f}%)")

    print(f"\n各风格详细结果:")
    for style_result in evaluation["styles"]:
        style = style_result["style"]
        agg = style_result["aggregate"]

        print(f"\n  {style}:")
        print(f"    风格匹配分数改进: {agg['improvement']['style_score']['mean']:+.2f}%")
        print(f"    BLEU-2 改进:      {agg['improvement']['bleu_2']['mean']:+.2f}%")
        print(f"    ROUGE-L 改进:     {agg['improvement']['rouge_l']['mean']:+.2f}%")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="评估风格迁移实验结果")
    parser.add_argument("results_file", type=str,
                        help="基准测试结果文件 (benchmark_*.json)")
    parser.add_argument("--output", type=str, default=None,
                        help="评估结果输出文件")

    args = parser.parse_args()

    # 运行评估
    evaluation = evaluate_benchmark_results(args.results_file)

    # 打印摘要
    print_evaluation_summary(evaluation)

    # 保存结果
    if args.output:
        output_file = args.output
    else:
        # 自动生成输出文件名
        input_path = Path(args.results_file)
        output_file = input_path.parent / f"evaluation_{input_path.stem}.json"

    save_evaluation(evaluation, str(output_file))
