"""
可视化实验结果

生成对比图表和 HTML 报告，直观展示微调效果
"""
import json
from pathlib import Path
from typing import Dict, List
import base64
from io import BytesIO


def generate_html_report(evaluation: Dict, benchmark: Dict, output_file: str):
    """生成 HTML 对比报告"""

    html_content = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>风格迁移微调效果对比报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', sans-serif;
            line-height: 1.6;
            background: #f5f7fa;
            color: #333;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        h1 { font-size: 2.5em; margin-bottom: 10px; }
        .subtitle { font-size: 1.1em; opacity: 0.9; }

        .summary {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .summary h2 { color: #667eea; margin-bottom: 20px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .stat-card {
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        .stat-label { color: #666; font-size: 0.9em; }

        .improvement {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        .improvement.positive {
            background: #d4edda;
            color: #155724;
        }
        .improvement.negative {
            background: #f8d7da;
            color: #721c24;
        }

        .style-section {
            background: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .style-section h3 {
            color: #667eea;
            font-size: 1.8em;
            margin-bottom: 20px;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
        }

        .metrics-table {
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }
        .metrics-table th,
        .metrics-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e1e8ed;
        }
        .metrics-table th {
            background: #f5f7fa;
            font-weight: 600;
            color: #667eea;
        }
        .metrics-table tr:hover {
            background: #f9fafb;
        }

        .comparison-box {
            background: #f9fafb;
            border-left: 4px solid #667eea;
            padding: 20px;
            margin: 20px 0;
            border-radius: 4px;
        }
        .comparison-box h4 {
            color: #667eea;
            margin-bottom: 10px;
        }
        .text-display {
            background: white;
            padding: 15px;
            border-radius: 4px;
            margin: 10px 0;
            border: 1px solid #e1e8ed;
            line-height: 1.8;
        }
        .text-label {
            font-weight: bold;
            color: #666;
            font-size: 0.9em;
            margin-bottom: 5px;
        }

        .baseline-tag { color: #ff6b6b; font-weight: bold; }
        .finetuned-tag { color: #51cf66; font-weight: bold; }

        footer {
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.9em;
        }

        .chart-placeholder {
            background: #f5f7fa;
            padding: 40px;
            text-align: center;
            border-radius: 8px;
            color: #999;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🎨 风格迁移微调效果对比报告</h1>
            <p class="subtitle">LoRA 微调 vs 基线模型性能对比分析</p>
        </header>
"""

    # 总体统计
    overall = evaluation["overall_summary"]
    html_content += f"""
        <div class="summary">
            <h2>📊 总体统计</h2>
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">测试风格数</div>
                    <div class="stat-value">{overall['total_styles']}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">测试案例数</div>
                    <div class="stat-value">{overall['total_cases']}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">平均风格分数改进</div>
                    <div class="stat-value">{overall['average_improvement']['style_score']['mean']:+.1f}%</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">平均 BLEU-2 改进</div>
                    <div class="stat-value">{overall['average_improvement']['bleu_2']['mean']:+.1f}%</div>
                </div>
            </div>
        </div>
"""

    # 各风格详细结果
    for style_eval in evaluation["styles"]:
        style = style_eval["style"]
        agg = style_eval["aggregate"]

        # 找到对应的 benchmark 数据
        style_benchmark = next((s for s in benchmark if s["style"] == style), None)

        html_content += f"""
        <div class="style-section">
            <h3>风格: {style}</h3>

            <h4>性能指标对比</h4>
            <table class="metrics-table">
                <thead>
                    <tr>
                        <th>指标</th>
                        <th>基线模型</th>
                        <th>微调模型</th>
                        <th>改进幅度</th>
                    </tr>
                </thead>
                <tbody>
"""

        metrics = [
            ("风格匹配分数", "style_score"),
            ("BLEU-2", "bleu_2"),
            ("ROUGE-L", "rouge_l"),
            ("词汇丰富度", "lexical_diversity"),
        ]

        for metric_label, metric_key in metrics:
            baseline_val = agg["baseline"][metric_key]["mean"]
            finetuned_val = agg["finetuned"][metric_key]["mean"]
            improvement = agg["improvement"][metric_key]["mean"]

            improvement_class = "positive" if improvement > 0 else "negative"

            html_content += f"""
                    <tr>
                        <td><strong>{metric_label}</strong></td>
                        <td>{baseline_val:.4f}</td>
                        <td>{finetuned_val:.4f}</td>
                        <td><span class="improvement {improvement_class}">{improvement:+.2f}%</span></td>
                    </tr>
"""

        html_content += """
                </tbody>
            </table>
"""

        # 显示测试案例示例（前2个）
        if style_benchmark and style_benchmark["test_cases"]:
            html_content += """
            <h4 style="margin-top: 30px;">生成样例对比</h4>
"""

            for i, case in enumerate(style_benchmark["test_cases"][:2], 1):
                html_content += f"""
            <div class="comparison-box">
                <h4>测试案例 {i}</h4>

                <div class="text-label">原文:</div>
                <div class="text-display">{case["original"]}</div>

                <div class="text-label"><span class="baseline-tag">基线模型</span> 生成:</div>
                <div class="text-display">{case["baseline"]["output"]}</div>

                <div class="text-label"><span class="finetuned-tag">微调模型</span> 生成:</div>
                <div class="text-display">{case["finetuned"]["output"]}</div>
            </div>
"""

        html_content += """
        </div>
"""

    html_content += """
        <footer>
            <p>报告生成时间: """ + evaluation["styles"][0]["cases"][0]["case_id"].__class__.__name__ + """</p>
            <p>由 NovelCraft 风格迁移实验系统自动生成</p>
        </footer>
    </div>
</body>
</html>
"""

    # 保存 HTML
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"\n✓ HTML 报告已生成: {output_path}")
    return output_path


def generate_comparison_table(evaluation: Dict) -> str:
    """生成 Markdown 格式的对比表格"""

    md_content = "# 风格迁移微调效果对比\n\n"
    md_content += "## 总体统计\n\n"

    overall = evaluation["overall_summary"]
    md_content += f"- **测试风格数**: {overall['total_styles']}\n"
    md_content += f"- **测试案例数**: {overall['total_cases']}\n\n"

    md_content += "### 平均改进率\n\n"
    md_content += "| 指标 | 改进幅度 | 标准差 |\n"
    md_content += "|------|---------|--------|\n"

    for metric, stats in overall["average_improvement"].items():
        md_content += f"| {metric} | {stats['mean']:+.2f}% | ±{stats['std']:.2f}% |\n"

    md_content += "\n## 各风格详细结果\n\n"

    for style_eval in evaluation["styles"]:
        style = style_eval["style"]
        agg = style_eval["aggregate"]

        md_content += f"### {style}\n\n"
        md_content += "| 指标 | 基线模型 | 微调模型 | 改进幅度 |\n"
        md_content += "|------|---------|---------|----------|\n"

        metrics = [
            ("风格匹配分数", "style_score"),
            ("BLEU-2", "bleu_2"),
            ("ROUGE-L", "rouge_l"),
            ("词汇丰富度", "lexical_diversity"),
        ]

        for metric_label, metric_key in metrics:
            baseline_val = agg["baseline"][metric_key]["mean"]
            finetuned_val = agg["finetuned"][metric_key]["mean"]
            improvement = agg["improvement"][metric_key]["mean"]

            md_content += f"| {metric_label} | {baseline_val:.4f} | {finetuned_val:.4f} | {improvement:+.2f}% |\n"

        md_content += "\n"

    return md_content


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="可视化实验结果")
    parser.add_argument("evaluation_file", type=str,
                        help="评估结果文件 (evaluation_*.json)")
    parser.add_argument("--benchmark", type=str, required=True,
                        help="基准测试结果文件 (benchmark_*.json)")
    parser.add_argument("--output", type=str, default="results/report.html",
                        help="输出 HTML 文件路径")
    parser.add_argument("--markdown", action="store_true",
                        help="同时生成 Markdown 格式报告")

    args = parser.parse_args()

    # 读取数据
    print("读取评估结果...")
    with open(args.evaluation_file, "r", encoding="utf-8") as f:
        evaluation = json.load(f)

    print("读取基准测试结果...")
    with open(args.benchmark, "r", encoding="utf-8") as f:
        benchmark = json.load(f)

    # 生成 HTML 报告
    print("\n生成 HTML 报告...")
    html_path = generate_html_report(evaluation, benchmark, args.output)

    # 生成 Markdown 报告
    if args.markdown:
        print("\n生成 Markdown 报告...")
        md_content = generate_comparison_table(evaluation)
        md_path = Path(args.output).with_suffix(".md")

        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        print(f"✓ Markdown 报告已生成: {md_path}")

    print("\n" + "="*70)
    print("可视化完成！")
    print("="*70)
    print(f"\n在浏览器中打开查看: {html_path}")
