"""
判断脚本 - 评估风格迁移测试结果

两层判断：
1. 自动指标（客观效率/稳定性）：空输出率、平均延迟、平均输出长度
2. 相似度指标（生成质量）：output 与 reference 的 ROUGE-L、BLEU-4、长度比
3. LLM 评判（语义相似度）：output 与 reference 的语义接近程度（调用 DeepSeek API）

用法：
  python judge_benchmark.py \
    --base results/benchmark_base_20260612_143000.json \
    --lora results/benchmark_lora_20260612_150000.json \
    --judge-api-key sk-xxxx
"""
import json
import re
import statistics
from collections import Counter
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from openai import OpenAI


# ============================================================
# 风格定义
# ============================================================

STYLE_DESCRIPTIONS = {
    "搞笑": "幽默诙谐，多用网络用语、夸张表达、反差梗，节奏轻快，读起来让人会心一笑",
    "古风": "文辞雅致，多用古语词汇和典故，意境深远，带有古典诗词的韵味和画面感",
    "言情": "细腻感性，注重心理描写和情感刻画，语言温柔缱绻，充满浪漫色彩",
}


# ============================================================
# 自动指标（效率/稳定性）
# ============================================================

def calc_auto_metrics(results: List[Dict]) -> Dict:
    """计算自动指标：空输出率、平均延迟、平均输出长度"""
    metrics = {}

    for style_result in results:
        style = style_result["style"]
        cases = style_result["test_cases"]

        total = len(cases)
        empty_count = sum(1 for c in cases if not c["output"].strip())
        latencies = [c["metadata"]["latency"] for c in cases]
        lengths = [len(c["output"]) for c in cases]

        metrics[style] = {
            "empty_rate": empty_count / total if total > 0 else 0,
            "avg_latency": statistics.mean(latencies) if latencies else 0,
            "avg_length": statistics.mean(lengths) if lengths else 0,
            "total_cases": total,
        }

    return metrics


def compare_auto_metrics(base_metrics: Dict, lora_metrics: Dict) -> Dict:
    """对比 base 和 lora 的自动指标"""
    comparison = {}
    all_styles = set(base_metrics.keys()) | set(lora_metrics.keys())

    for style in all_styles:
        b = base_metrics.get(style, {})
        l = lora_metrics.get(style, {})

        b_latency = b.get("avg_latency", 0)
        l_latency = l.get("avg_latency", 0)

        comparison[style] = {
            "base_empty_rate": b.get("empty_rate", None),
            "lora_empty_rate": l.get("empty_rate", None),
            "base_avg_latency": b_latency,
            "lora_avg_latency": l_latency,
            "latency_change": (l_latency - b_latency) / b_latency * 100 if b_latency > 0 else 0,
            "base_avg_length": b.get("avg_length", None),
            "lora_avg_length": l.get("avg_length", None),
        }

    return comparison


# ============================================================
# 相似度指标（output vs reference）
# ============================================================

def _lcs_length(s1: List[str], s2: List[str]) -> int:
    """计算两个序列的最长公共子序列长度"""
    m, n = len(s1), len(s2)
    if m == 0 or n == 0:
        return 0
    # 优化空间：只用两行
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)
    return prev[n]


def calc_rouge_l(output: str, reference: str) -> float:
    """计算 ROUGE-L F1 分数（基于字符级 LCS）

    ROUGE-L = (1 + beta^2) * P * R / (beta^2 * P + R)
    beta=1 时即 F1
    """
    if not output.strip() or not reference.strip():
        return 0.0

    out_chars = list(output)
    ref_chars = list(reference)

    lcs_len = _lcs_length(out_chars, ref_chars)

    if lcs_len == 0:
        return 0.0

    precision = lcs_len / len(out_chars)
    recall = lcs_len / len(ref_chars)

    if precision + recall == 0:
        return 0.0

    f1 = 2 * precision * recall / (precision + recall)
    return f1


def calc_bleu4(output: str, reference: str) -> float:
    """计算 BLEU-4 分数（基于字符级 n-gram 精确率）

    BLEU-4 = brevity_penalty * exp(avg(log(p_n))) for n=1..4
    衡量 output 中的 n-gram 有多少命中 reference（精确导向）
    """
    if not output.strip() or not reference.strip():
        return 0.0

    out_chars = list(output)
    ref_chars = list(reference)

    # 计算 1-gram 到 4-gram 的修改后精确率
    precisions = []
    for n in range(1, 5):
        out_ngrams = [tuple(out_chars[i:i + n]) for i in range(len(out_chars) - n + 1)]
        ref_ngrams = [tuple(ref_chars[i:i + n]) for i in range(len(ref_chars) - n + 1)]

        if not out_ngrams:
            precisions.append(0.0)
            continue

        ref_counts = Counter(ref_ngrams)
        out_counts = Counter(out_ngrams)

        # 修改后精确率：每个 n-gram 最多匹配 ref 中出现的次数
        clipped = sum(min(count, ref_counts.get(ngram, 0)) for ngram, count in out_counts.items())
        total = sum(out_counts.values())

        precisions.append(clipped / total if total > 0 else 0.0)

    # 如果任何 n-gram 精确率为 0，BLEU-4 为 0
    if any(p == 0 for p in precisions):
        return 0.0

    # 几何平均
    log_avg = sum(statistics.log(p) for p in precisions) / 4
    geo_avg = statistics.exp(log_avg)

    # 简短惩罚
    bp = 1.0
    if len(out_chars) < len(ref_chars):
        bp = statistics.exp(1 - len(ref_chars) / len(out_chars))

    return bp * geo_avg


def calc_length_ratio(output: str, reference: str) -> float:
    """计算长度比（output 长度 / reference 长度）

    反映结构性差异：过短可能遗漏内容，过长可能添加冗余
    返回值越接近 1.0 越好，用 min(ratio, 1/ratio) 映射到 [0, 1]
    """
    if not output.strip() or not reference.strip():
        return 0.0

    ratio = len(output) / len(reference)
    # 映射到 [0, 1]：1.0 为最佳，偏离越远分数越低
    return min(ratio, 1.0 / ratio) if ratio > 0 else 0.0


def calc_similarity_metrics(output: str, reference: str) -> Dict:
    """计算 output 与 reference 之间的所有相似度指标"""
    return {
        "rouge_l": round(calc_rouge_l(output, reference), 4),
        "bleu4": round(calc_bleu4(output, reference), 4),
        "length_ratio": round(calc_length_ratio(output, reference), 4),
    }


def calc_all_similarity(results: List[Dict]) -> Dict:
    """计算所有风格的相似度指标汇总

    Returns:
        {style: {avg_rouge_l, avg_bleu4, avg_length_ratio, cases: [{id, scores}]}}
    """
    metrics = {}

    for style_result in results:
        style = style_result["style"]
        cases = style_result["test_cases"]

        case_metrics = []
        for case in cases:
            sim = calc_similarity_metrics(case["output"], case.get("reference", ""))
            case_metrics.append({
                "id": case["id"],
                "scores": sim,
            })

        rouge_ls = [c["scores"]["rouge_l"] for c in case_metrics]
        bleu4s = [c["scores"]["bleu4"] for c in case_metrics]
        length_ratios = [c["scores"]["length_ratio"] for c in case_metrics]

        metrics[style] = {
            "avg_rouge_l": statistics.mean(rouge_ls) if rouge_ls else 0,
            "avg_bleu4": statistics.mean(bleu4s) if bleu4s else 0,
            "avg_length_ratio": statistics.mean(length_ratios) if length_ratios else 0,
            "cases": case_metrics,
        }

    return metrics


def compare_similarity(base_sim: Dict, lora_sim: Dict) -> Dict:
    """对比 base 和 lora 的相似度指标"""
    comparison = {}
    all_styles = set(base_sim.keys()) | set(lora_sim.keys())

    for style in all_styles:
        b = base_sim.get(style, {})
        l = lora_sim.get(style, {})

        b_rouge = b.get("avg_rouge_l", 0)
        l_rouge = l.get("avg_rouge_l", 0)
        b_bleu = b.get("avg_bleu4", 0)
        l_bleu = l.get("avg_bleu4", 0)
        b_len = b.get("avg_length_ratio", 0)
        l_len = l.get("avg_length_ratio", 0)

        comparison[style] = {
            "base_avg_rouge_l": b_rouge,
            "lora_avg_rouge_l": l_rouge,
            "rouge_l_change": l_rouge - b_rouge,
            "base_avg_bleu4": b_bleu,
            "lora_avg_bleu4": l_bleu,
            "bleu4_change": l_bleu - b_bleu,
            "base_avg_length_ratio": b_len,
            "lora_avg_length_ratio": l_len,
            "length_ratio_change": l_len - b_len,
        }

    return comparison


# ============================================================
# LLM 评判（output vs reference 语义相似度）
# ============================================================

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-pro"

JUDGE_PROMPT = """你是一位专业的文学评论家。请评估以下风格转换的输出结果与参考答案之间的相似程度。

【目标风格】{style_name}
【风格特征说明】{style_description}

【原文】
{original}

【参考答案（期望的风格转换结果）】
{reference}

【模型输出（实际生成的结果）】
{output}

请从以下维度评分（1-5分），并简要说明理由：

1. 语义相似度：模型输出与参考答案在核心内容、情节、人物对话上是否一致？（1=完全不同，5=高度一致）
2. 风格匹配度：模型输出的风格是否与参考答案的风格水平接近？（1=风格完全不同，5=风格高度一致）
3. 表达质量：模型输出的语言组织是否自然流畅，与参考答案的文笔质量相当？（1=极差，5=优秀）

请严格以 JSON 格式输出，不要添加任何其他内容：
{{"semantic_similarity": <1-5>, "style_match": <1-5>, "expression_quality": <1-5>, "comment": "<一句话点评>"}}"""


def _parse_llm_json(content: str) -> Dict:
    """解析 LLM 返回的 JSON，兼容各种格式异常"""
    # 直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 从 markdown 代码块提取
    match = re.search(r'```(?:json)?\s*([\s\S]*?)```', content)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 提取包含目标字段的 JSON 对象
    for pattern in [
        r'\{[^{}]*"semantic_similarity"[^{}]*\}',
        r'\{[\s\S]*\}',
    ]:
        matches = list(re.finditer(pattern, content))
        if matches:
            try:
                return json.loads(matches[-1].group(0))
            except json.JSONDecodeError:
                continue

    print(f"  [警告] LLM 评判返回格式异常，使用默认最低分: {content[:100]}...")
    return {
        "semantic_similarity": 1,
        "style_match": 1,
        "expression_quality": 1,
        "comment": "解析失败",
    }


def llm_judge_single(
    original: str,
    output: str,
    reference: str,
    style_name: str,
    client: OpenAI,
    model: str = DEEPSEEK_MODEL,
) -> Dict:
    """调用 DeepSeek API 评判 output 与 reference 的相似度"""
    if not output.strip():
        return {
            "semantic_similarity": 1,
            "style_match": 1,
            "expression_quality": 1,
            "comment": "输出为空",
        }

    prompt = JUDGE_PROMPT.format(
        style_name=style_name,
        style_description=STYLE_DESCRIPTIONS.get(style_name, ""),
        original=original,
        reference=reference,
        output=output,
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "你是一位专业的文学评论家。请严格按照用户要求的 JSON 格式输出，不要输出任何其他内容。"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=1024,
    )
    content = response.choices[0].message.content or ""

    scores = _parse_llm_json(content)

    # 确保分数在 1-5 范围内
    for key in ["semantic_similarity", "style_match", "expression_quality"]:
        scores[key] = max(1, min(5, int(scores.get(key, 1))))

    return scores


def llm_judge_all(
    base_results: List[Dict],
    lora_results: List[Dict],
    client: OpenAI,
    model: str = DEEPSEEK_MODEL,
    styles: Optional[List[str]] = None,
    max_cases: int = 30,
) -> Dict:
    """用 DeepSeek API 评判所有 base 和 lora 的 output 与 reference 的相似度

    Args:
        max_cases: 每个风格最多评判的用例数（均匀采样）

    Returns:
        {style: {base: {cases: [...], summary: ...}, lora: {cases: [...], summary: ...}}}
    """
    index = {}
    for r in base_results:
        index.setdefault(r["style"], {})["base"] = r
    for r in lora_results:
        index.setdefault(r["style"], {})["lora"] = r

    styles_to_test = styles if styles else list(index.keys())
    judge_results = {}

    for style in styles_to_test:
        if style not in index:
            print(f"  [跳过] 风格 '{style}' 在结果中不存在")
            continue

        print(f"\n  LLM 评判风格: {style}")

        judge_results[style] = {"base": {"cases": []}, "lora": {"cases": []}}

        for model_type in ["base", "lora"]:
            if model_type not in index[style]:
                continue

            result = index[style][model_type]
            cases = result["test_cases"]

            # 限制用例数：均匀采样
            if len(cases) > max_cases:
                step = len(cases) / max_cases
                indices = [int(i * step) for i in range(max_cases)]
                cases = [cases[i] for i in indices]
                print(f"    [{model_type}] 用例数 {len(result['test_cases'])} > {max_cases}，均匀采样 {len(cases)} 个")

            for i, case in enumerate(cases):
                print(f"    [{model_type}] 案例 {i + 1}/{len(cases)}...")

                scores = llm_judge_single(
                    original=case["original"],
                    output=case["output"],
                    reference=case.get("reference", ""),
                    style_name=style,
                    client=client,
                    model=model,
                )

                judge_results[style][model_type]["cases"].append({
                    "id": case["id"],
                    "scores": scores,
                })

    # 计算汇总统计
    for style in judge_results:
        for model_type in ["base", "lora"]:
            cases = judge_results[style][model_type]["cases"]
            if not cases:
                judge_results[style][model_type]["summary"] = None
                continue

            sem_sims = [c["scores"]["semantic_similarity"] for c in cases]
            style_matches = [c["scores"]["style_match"] for c in cases]
            expr_quality = [c["scores"]["expression_quality"] for c in cases]

            judge_results[style][model_type]["summary"] = {
                "avg_semantic_similarity": statistics.mean(sem_sims),
                "avg_style_match": statistics.mean(style_matches),
                "avg_expression_quality": statistics.mean(expr_quality),
                "pass_rate": sum(
                    1 for c in cases
                    if c["scores"]["semantic_similarity"] >= 3
                    and c["scores"]["style_match"] >= 3
                    and c["scores"]["expression_quality"] >= 3
                ) / len(cases),
            }

    return judge_results


# ============================================================
# 综合判定
# ============================================================

def make_verdict(
    auto_comparison: Dict,
    sim_comparison: Dict,
    llm_judge: Dict,
) -> Dict:
    """综合自动指标、相似度指标和 LLM 评判，给出最终判定"""

    style_verdicts = {}

    for style in sim_comparison:
        sim = sim_comparison[style]
        auto = auto_comparison.get(style, {})

        # 相似度指标（核心判定依据）
        lora_rouge = sim.get("lora_avg_rouge_l", 0)
        lora_bleu4 = sim.get("lora_avg_bleu4", 0)
        lora_length_ratio = sim.get("lora_avg_length_ratio", 0)

        # 综合相似度 = 三个指标的加权平均
        composite_similarity = (
            lora_rouge * 0.4
            + lora_bleu4 * 0.4
            + lora_length_ratio * 0.2
        )

        # 相似度判定：综合相似度 >= 0.3 为通过
        sim_pass = composite_similarity >= 0.3

        # 自动指标判定：空输出率 < 10%
        lora_empty = auto.get("lora_empty_rate", 0)
        auto_pass = lora_empty is not None and lora_empty < 0.10

        # LLM 评判（如有）
        llm_pass = True
        llm_details = {}
        if style in llm_judge:
            lora_summary = llm_judge[style]["lora"].get("summary") or {}
            base_summary = llm_judge[style]["base"].get("summary") or {}

            lora_sem = lora_summary.get("avg_semantic_similarity", 0)
            lora_style = lora_summary.get("avg_style_match", 0)
            lora_expr = lora_summary.get("avg_expression_quality", 0)

            llm_pass = lora_sem >= 3.0 and lora_style >= 3.0 and lora_expr >= 3.0

            base_sem = base_summary.get("avg_semantic_similarity", 0)
            llm_details = {
                "lora_avg_semantic_similarity": lora_sem,
                "lora_avg_style_match": lora_style,
                "lora_avg_expression_quality": lora_expr,
                "semantic_improvement": lora_sem - base_sem,
            }

        # 改进判定（lora vs base）
        base_rouge = sim.get("base_avg_rouge_l", 0)
        rouge_improved = lora_rouge > base_rouge if base_rouge > 0 else True

        verdict = "PASS" if (sim_pass and auto_pass and llm_pass) else "FAIL"

        style_verdicts[style] = {
            "sim_pass": sim_pass,
            "auto_pass": auto_pass,
            "llm_pass": llm_pass,
            "rouge_improved": rouge_improved,
            "verdict": verdict,
            "details": {
                "composite_similarity": round(composite_similarity, 4),
                "lora_avg_rouge_l": lora_rouge,
                "lora_avg_bleu4": lora_bleu4,
                "lora_avg_length_ratio": lora_length_ratio,
                "lora_empty_rate": lora_empty,
                "rouge_l_improvement": round(lora_rouge - base_rouge, 4),
                **llm_details,
            },
        }

    overall_pass = sum(1 for v in style_verdicts.values() if v["verdict"] == "PASS")
    total = len(style_verdicts)

    if total == 0:
        overall_verdict = "FAIL"
    elif overall_pass == total:
        overall_verdict = "PASS"
    elif overall_pass >= total * 0.5:
        overall_verdict = "PARTIAL"
    else:
        overall_verdict = "FAIL"

    return {
        "overall_verdict": overall_verdict,
        "pass_count": overall_pass,
        "total_styles": total,
        "styles": style_verdicts,
    }


# ============================================================
# 主流程
# ============================================================

def strip_thinking_tags(text: str) -> str:
    """去掉 output 中的 <think>...</think> 标签及其内容"""
    if not text:
        return text
    return re.sub(r'<think>[\s\S]*?</think>\s*', '', text, flags=re.IGNORECASE)


def load_results(filepath: str) -> List[Dict]:
    """加载 benchmark 结果 JSON，并清理 output 中的 thinking/response 标签"""
    with open(filepath, "r", encoding="utf-8") as f:
        results = json.load(f)

    for style_result in results:
        for case in style_result.get("test_cases", []):
            if "output" in case:
                case["output"] = strip_thinking_tags(case["output"])

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(description="评估风格迁移测试结果")
    parser.add_argument("--base", type=str, required=True,
                        help="基线模型测试结果 JSON")
    parser.add_argument("--lora", type=str, required=True,
                        help="LoRA 微调模型测试结果 JSON")
    parser.add_argument("--judge-api-key", type=str, default=None,
                        help="DeepSeek API Key（不指定则跳过 LLM 评判）")
    parser.add_argument("--judge-base-url", type=str, default=DEEPSEEK_BASE_URL,
                        help=f"DeepSeek API 地址（默认: {DEEPSEEK_BASE_URL}）")
    parser.add_argument("--judge-model", type=str, default=DEEPSEEK_MODEL,
                        help=f"评判模型名（默认: {DEEPSEEK_MODEL}）")
    parser.add_argument("--styles", type=str, nargs="+",
                        choices=list(STYLE_DESCRIPTIONS.keys()),
                        help="只评判指定风格（默认全部）")
    parser.add_argument("--output", type=str, default=None,
                        help="输出文件路径（默认自动生成）")
    parser.add_argument("--max-cases", type=int, default=10,
                        help="LLM 评判每个风格最多用例数（默认: 10，均匀采样）")

    args = parser.parse_args()

    # 加载结果
    print("=" * 70)
    print("风格迁移测试结果评估")
    print("=" * 70)

    print("\n加载测试结果...")
    base_results = load_results(args.base)
    lora_results = load_results(args.lora)
    print(f"  基线模型: {len(base_results)} 个风格, {sum(len(r['test_cases']) for r in base_results)} 个案例")
    print(f"  LoRA模型: {len(lora_results)} 个风格, {sum(len(r['test_cases']) for r in lora_results)} 个案例")

    # ========================================
    # 第一层：自动指标
    # ========================================
    print("\n" + "-" * 40)
    print("第一层：自动指标（效率/稳定性）")
    print("-" * 40)

    base_auto = calc_auto_metrics(base_results)
    lora_auto = calc_auto_metrics(lora_results)
    auto_comparison = compare_auto_metrics(base_auto, lora_auto)

    for style, metrics in auto_comparison.items():
        print(f"\n  [{style}]")
        print(f"    空输出率:  base={metrics['base_empty_rate']:.0%}, lora={metrics['lora_empty_rate']:.0%}")
        print(f"    平均延迟:  base={metrics['base_avg_latency']:.2f}s, lora={metrics['lora_avg_latency']:.2f}s ({metrics['latency_change']:+.1f}%)")
        print(f"    平均长度:  base={metrics['base_avg_length']:.0f}字, lora={metrics['lora_avg_length']:.0f}字")

    # ========================================
    # 第二层：相似度指标（output vs reference）
    # ========================================
    print("\n" + "-" * 40)
    print("第二层：相似度指标（output vs reference）")
    print("-" * 40)

    base_sim = calc_all_similarity(base_results)
    lora_sim = calc_all_similarity(lora_results)
    sim_comparison = compare_similarity(base_sim, lora_sim)

    for style, metrics in sim_comparison.items():
        print(f"\n  [{style}]")
        print(f"    ROUGE-L:    base={metrics['base_avg_rouge_l']:.4f}, lora={metrics['lora_avg_rouge_l']:.4f} ({metrics['rouge_l_change']:+.4f})")
        print(f"    BLEU-4:     base={metrics['base_avg_bleu4']:.4f}, lora={metrics['lora_avg_bleu4']:.4f} ({metrics['bleu4_change']:+.4f})")
        print(f"    长度比:     base={metrics['base_avg_length_ratio']:.4f}, lora={metrics['lora_avg_length_ratio']:.4f} ({metrics['length_ratio_change']:+.4f})")

    # ========================================
    # 第三层：LLM 评判（DeepSeek API）
    # ========================================
    llm_judge_results = {}

    if args.judge_api_key:
        print("\n" + "-" * 40)
        print("第三层：LLM 评判（output vs reference 语义相似度）")
        print("-" * 40)
        print(f"  模型: {args.judge_model}")
        print(f"  API:  {args.judge_base_url}")

        client = OpenAI(
            api_key=args.judge_api_key,
            base_url=args.judge_base_url,
        )

        llm_judge_results = llm_judge_all(
            base_results=base_results,
            lora_results=lora_results,
            client=client,
            model=args.judge_model,
            styles=args.styles,
            max_cases=args.max_cases,
        )

        for style, data in llm_judge_results.items():
            for model_type in ["base", "lora"]:
                summary = data[model_type].get("summary")
                if summary:
                    print(f"\n  [{style}] {model_type}:")
                    print(f"    语义相似度: {summary['avg_semantic_similarity']:.2f}")
                    print(f"    风格匹配度: {summary['avg_style_match']:.2f}")
                    print(f"    表达质量:   {summary['avg_expression_quality']:.2f}")
                    print(f"    案例通过率: {summary['pass_rate']:.0%}")
    else:
        print("\n  [跳过] LLM 评判（未指定 --judge-api-key）")

    # ========================================
    # 综合判定
    # ========================================
    print("\n" + "=" * 70)
    print("综合判定")
    print("=" * 70)

    verdict = make_verdict(auto_comparison, sim_comparison, llm_judge_results)

    print(f"\n  总体判定: {verdict['overall_verdict']}")
    print(f"  通过风格: {verdict['pass_count']}/{verdict['total_styles']}")

    for style, v in verdict["styles"].items():
        details = v["details"]
        print(f"\n  [{style}] {v['verdict']}")
        print(f"    综合相似度: {details['composite_similarity']:.4f}")
        print(f"    ROUGE-L: {details['lora_avg_rouge_l']:.4f}, "
              f"BLEU-4: {details['lora_avg_bleu4']:.4f}, "
              f"长度比: {details['lora_avg_length_ratio']:.4f}")
        print(f"    空输出率: {details['lora_empty_rate']:.0%}")
        if details["rouge_l_improvement"] > 0:
            print(f"    ROUGE-L 提升: +{details['rouge_l_improvement']:.4f}")
        if "lora_avg_semantic_similarity" in details:
            print(f"    LLM: 语义相似度={details['lora_avg_semantic_similarity']:.2f}, "
                  f"风格匹配度={details['lora_avg_style_match']:.2f}, "
                  f"表达质量={details['lora_avg_expression_quality']:.2f}")

    # ========================================
    # 保存报告
    # ========================================
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = args.output or f"results/judge_report_{timestamp}.json"

    report = {
        "timestamp": datetime.now().isoformat(),
        "input": {
            "base_file": args.base,
            "lora_file": args.lora,
        },
        "auto_metrics": auto_comparison,
        "similarity_metrics": {
            "base": {style: {"avg_rouge_l": d["avg_rouge_l"], "avg_bleu4": d["avg_bleu4"], "avg_length_ratio": d["avg_length_ratio"], "cases": d["cases"]} for style, d in base_sim.items()},
            "lora": {style: {"avg_rouge_l": d["avg_rouge_l"], "avg_bleu4": d["avg_bleu4"], "avg_length_ratio": d["avg_length_ratio"], "cases": d["cases"]} for style, d in lora_sim.items()},
            "comparison": sim_comparison,
        },
        "llm_judge": {
            style: {
                model_type: {
                    "summary": data[model_type].get("summary"),
                    "cases": data[model_type]["cases"],
                }
                for model_type in ["base", "lora"]
            }
            for style, data in llm_judge_results.items()
        } if llm_judge_results else {},
        "verdict": verdict,
    }

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n报告已保存到: {output_path}")


if __name__ == "__main__":
    main()
