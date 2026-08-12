"""
对比实验脚本 - 测试部署的模型（基线或 LoRA 微调）

适配 swift deploy 部署的服务，统一访问所有部署的模型

核心功能：
1. 自动查询部署服务中可用的模型
2. 对指定模型进行风格迁移测试
3. 通过 --model-label 参数标识模型类型（如 base/lora），用于结果文件命名
"""
import asyncio
import httpx
import json
from typing import Dict, List, Tuple
from pathlib import Path
from datetime import datetime
import statistics


# 风格映射：英文 -> 中文
STYLE_MAP = {
    "gaoxiao": "搞笑",
    "gufeng": "古风",
    "yanqing": "言情",
}

# 中文风格列表
STYLE_NAMES = list(STYLE_MAP.values())


class StyleTransferBenchmark:
    """风格迁移测试实验"""

    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.available_models = []
        self.model_label = None  # 模型标签（用于输出文件名）

    async def discover_models(self) -> List[str]:
        """从部署服务中获取所有可用模型"""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(f"{self.api_url}/v1/models")
                resp.raise_for_status()
                model_list = resp.json().get("data", [])
            except Exception as e:
                print(f"错误: 无法连接到 {self.api_url}/v1/models")
                print(f"  {e}")
                print("\n请先启动部署服务:")
                print("  bash scripts/deploy_vllm.sh")
                raise

        self.available_models = [m["id"] for m in model_list]
        return self.available_models

    async def generate_text(
        self,
        text: str,
        style_name: str,
        model_id: str,
        temperature: float = 0.7,
    ) -> Tuple[str, Dict]:
        """生成文本并记录元数据

        Args:
            text: 原始文本
            style_name: 风格中文名（用于构造 prompt）
            model_id: 模型 ID
        """
        system_prompt = f"""你是一位专业的文学风格转换专家，擅长将文本转换为{style_name}的写作风格。

转换要求：
1. 保持原文的核心内容和情节不变
2. 充分体现{style_name}的语言特色和叙事风格
3. 注意句式、用词、节奏的风格化处理
4. 保持文本的流畅性和可读性
5. 只输出转换后的文本，不要添加任何解释或说明"""

        user_prompt = f"请将以下文本转换为{style_name}的写作风格：\n\n{text}"

        request_data = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "top_p": 0.9,
            "max_tokens": len(text) * 3,
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            start_time = asyncio.get_event_loop().time()

            response = await client.post(
                f"{self.api_url}/v1/chat/completions",
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()

            end_time = asyncio.get_event_loop().time()

            transformed = result["choices"][0]["message"]["content"]

            metadata = {
                "latency": end_time - start_time,
                "model_id": model_id,
                "tokens": result.get("usage", {}).get("completion_tokens", 0),
            }

            return transformed, metadata

    async def run_single_style_benchmark(
        self,
        test_cases: List[Dict[str, str]],
        style_name: str,
        model_id: str,
    ) -> Dict:
        """运行单个风格的测试"""

        print(f"\n{'='*70}")
        print(f"测试风格: {style_name}")
        print(f"  模型标签: {self.model_label}")
        print(f"  模型 ID:  {model_id}")
        print(f"{'='*70}\n")

        result = {
            "style": style_name,
            "model_label": self.model_label,
            "model_id": model_id,
            "test_cases": [],
            "timestamp": datetime.now().isoformat(),
        }

        for i, test_case in enumerate(test_cases, 1):
            original_text = test_case["text"]
            reference_text = test_case.get("reference", None)

            print(f"\n测试案例 {i}/{len(test_cases)}")
            print(f"原文: {original_text[:50]}...")

            output, meta = await self.generate_text(
                original_text, style_name, model_id=model_id
            )

            case_result = {
                "id": i,
                "original": original_text,
                "reference": reference_text,
                "output": output,
                "metadata": meta,
            }

            result["test_cases"].append(case_result)

            print(f"  完成 (延迟: {meta['latency']:.2f}s)")

        return result

    async def run_multi_style_benchmark(
        self,
        test_cases: List[Dict[str, str]],
        model_id: str,
        styles: List[str] = None,
    ) -> List[Dict]:
        """运行多风格测试"""

        all_results = []
        styles_to_test = styles if styles else STYLE_NAMES

        for style_input in styles_to_test:
            # 转换英文到中文（如果是英文输入）
            style_name = STYLE_MAP.get(style_input.lower(), style_input)

            result = await self.run_single_style_benchmark(
                test_cases, style_name, model_id
            )
            all_results.append(result)
            await asyncio.sleep(1)

        return all_results

    def save_results(self, results: List[Dict], output_file: str = "benchmark_results.json"):
        """保存实验结果"""
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"\n结果已保存到: {output_path}")
        return output_path

    def print_summary(self, results: List[Dict]):
        """打印实验摘要"""

        print("\n" + "="*70)
        print("实验摘要")
        print("="*70)

        for result in results:
            style = result["style"]
            test_cases = result["test_cases"]

            latencies = [tc["metadata"]["latency"] for tc in test_cases]
            tokens = [tc["metadata"]["tokens"] for tc in test_cases]

            print(f"\n风格: {style}")
            print(f"  模型标签: {result.get('model_label', 'N/A')}")
            print(f"  测试案例数: {len(test_cases)}")
            print(f"  平均延迟: {statistics.mean(latencies):.2f}s")
            print(f"  平均输出token: {statistics.mean(tokens):.0f}")


def load_test_cases(test_file: str = None) -> List[Dict[str, str]]:
    """加载测试案例

    支持两种格式：
    1. jsonl messages 格式: {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
    2. 简单格式: {"text": "...", "reference": "..."}
    """
    if test_file and Path(test_file).exists():
        cases = []

        # 尝试按 jsonl 读取（每行一个 JSON）
        with open(test_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)

                # messages 格式：提取 user 输入和 assistant 参考输出
                if "messages" in data:
                    user_content = ""
                    reference = ""
                    for msg in data["messages"]:
                        if msg["role"] == "user":
                            user_content = msg["content"]
                            # 去掉 "请将以下文本转换为XX风格：" 前缀，提取纯文本
                            prefix_match = user_content.find("：\n\n")
                            if prefix_match != -1:
                                user_content = user_content[prefix_match + 3:]
                        elif msg["role"] == "assistant":
                            reference = msg["content"]
                    cases.append({"text": user_content, "reference": reference})

                # 简单格式
                elif "text" in data:
                    cases.append(data)

        if cases:
            print(f"从 {test_file} 加载了 {len(cases)} 条测试案例")
            return cases

    print("使用默认测试案例")
    return [
        {
            "text": "夜色渐深，街道上的行人越来越少，只剩下远处几盏昏黄的灯光在风中摇曳。一个黑衣人从巷子里走出来，他的脚步很轻，几乎没有声音。",
        },
        {
            "text": "她站在窗前，看着外面的雨。雨下得很大，打在玻璃上啪啪作响。她想起了很多年前的那个下雨天，想起了那个已经离开的人。",
        },
        {
            "text": "剑光一闪，血花飞溅。胜负已分，生死已定。胜者收剑而立，败者倒地不起。江湖就是这样，没有第二次机会。",
        },
        {
            "text": "清晨的阳光洒在书桌上，照亮了摊开的书页。窗外传来鸟鸣声，清脆悦耳。这是一个适合读书的好日子。",
        },
        {
            "text": "他打开门，房间里空无一人。桌上的茶还冒着热气，显然主人刚刚离开不久。空气中弥漫着淡淡的香味，是她惯用的那种香水。",
        },
    ]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="运行风格迁移测试实验")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000",
                        help="swift deploy 服务地址")
    parser.add_argument("--model-id", type=str, default=None,
                        help="要测试的模型 ID（不指定则使用第一个可用模型）")
    parser.add_argument("--model-label", type=str, required=True,
                        help="模型标签（如 base/lora），用于输出文件命名")
    parser.add_argument("--test-file", type=str, default=None,
                        help="测试集文件路径")
    parser.add_argument("--quick", action="store_true",
                        help="快速模式（仅测试前2个案例）")
    parser.add_argument("--styles", type=str, nargs="+",
                        help="只测试指定风格（默认全部）")

    args = parser.parse_args()

    benchmark = StyleTransferBenchmark(args.api_url)
    benchmark.model_label = args.model_label

    # 自动发现可用模型
    print("="*70)
    print(f"风格迁移测试实验 (模型标签: {args.model_label})")
    print("="*70)
    print("\n正在查询部署服务中的可用模型...")

    models = await benchmark.discover_models()
    print(f"  可用模型: {', '.join(models)}")

    # 如果未指定模型，使用第一个
    if args.model_id is None:
        if not models:
            print("\n错误: 没有发现任何可用模型")
            return
        args.model_id = models[0]
        print(f"\n未指定模型，自动使用: {args.model_id}")
    else:
        # 验证指定的模型是否存在
        if args.model_id not in models:
            print(f"\n错误: 指定的模型 '{args.model_id}' 不在可用模型列表中")
            print(f"可用模型: {models}")
            return

    # 加载测试案例
    test_cases = load_test_cases(args.test_file)
    if args.quick:
        test_cases = test_cases[:2]
        print("\n快速模式：仅测试前 2 个案例")

    # 计算测试规模
    styles_count = len(args.styles) if args.styles else len(STYLE_NAMES)

    print(f"\n测试模型: {args.model_id}")
    print(f"测试案例数: {len(test_cases)}")
    print(f"测试风格数: {styles_count}")
    print(f"总测试次数: {len(test_cases) * styles_count}")

    # 运行实验
    results = await benchmark.run_multi_style_benchmark(
        test_cases, args.model_id, args.styles
    )

    # 保存结果：文件名包含时间戳和模型标签
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"results/benchmark_{args.model_label}_{timestamp}.json"
    benchmark.save_results(results, output_file)

    # 打印摘要
    benchmark.print_summary(results)

    print("\n" + "="*70)
    print("实验完成！")
    print("="*70)
    print(f"\n详细结果: {output_file}")
    print(f"提示: 如需对比效果，请用不同的 --model-id 和 --model-label 再运行一次，")
    print(f"      然后用 judge_benchmark.py 对两次结果进行对比评估。")


if __name__ == "__main__":
    asyncio.run(main())
