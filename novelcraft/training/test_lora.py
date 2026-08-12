"""
LoRA 模型测试脚本

用于测试训练好的 LoRA 适配器效果
"""
import asyncio
import httpx
from typing import Optional


async def test_style_transfer(
    text: str,
    style_name: str,
    lora_adapter: str,
    vllm_url: str = "http://localhost:8000",
):
    """测试风格迁移效果

    Args:
        text: 原始文本
        style_name: 风格名称（如"古龙"）
        lora_adapter: LoRA 适配器名称（如"gulong-style-lora"）
        vllm_url: vLLM 服务地址
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
        "model": "Qwen/Qwen3-8B-Instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": len(text) * 3,
        "extra_body": {
            "lora_adapter": lora_adapter
        }
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print(f"\n{'='*60}")
            print(f"测试风格: {style_name} (LoRA: {lora_adapter})")
            print(f"{'='*60}")
            print(f"\n原文:\n{text}")
            print(f"\n正在转换...")

            response = await client.post(
                f"{vllm_url}/v1/chat/completions",
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()

            transformed = result["choices"][0]["message"]["content"]

            print(f"\n转换后:\n{transformed}")
            print(f"\n{'='*60}\n")

            return transformed

        except Exception as e:
            print(f"\n❌ 测试失败: {e}\n")
            return None


async def compare_styles(text: str, vllm_url: str = "http://localhost:8000"):
    """对比不同风格的转换效果"""

    styles = [
        ("古龙", "gulong-style-lora"),
        ("曹文轩", "caowenxuan-style-lora"),
        ("金庸", "jinyong-style-lora"),
        ("刘慈欣", "liubixin-style-lora"),
        ("王小波", "wangxiaobo-style-lora"),
        ("鲁迅", "luxun-style-lora"),
    ]

    print("\n" + "="*60)
    print("多风格对比测试")
    print("="*60)
    print(f"\n原文:\n{text}\n")

    for style_name, lora_adapter in styles:
        await test_style_transfer(text, style_name, lora_adapter, vllm_url)
        await asyncio.sleep(1)  # 避免请求过快


async def test_with_base_model(
    text: str,
    style_name: str,
    vllm_url: str = "http://localhost:8000",
):
    """使用基础模型（不加载 LoRA）进行测试，作为对比基线"""

    system_prompt = f"""你是一位专业的文学风格转换专家，擅长将文本转换为{style_name}的写作风格。

转换要求：
1. 保持原文的核心内容和情节不变
2. 充分体现{style_name}的语言特色和叙事风格
3. 注意句式、用词、节奏的风格化处理
4. 保持文本的流畅性和可读性
5. 只输出转换后的文本，不要添加任何解释或说明"""

    user_prompt = f"请将以下文本转换为{style_name}的写作风格：\n\n{text}"

    request_data = {
        "model": "Qwen/Qwen3-8B-Instruct",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": len(text) * 3,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print(f"\n{'='*60}")
            print(f"基线测试: {style_name} (无 LoRA)")
            print(f"{'='*60}")
            print(f"\n原文:\n{text}")
            print(f"\n正在转换...")

            response = await client.post(
                f"{vllm_url}/v1/chat/completions",
                json=request_data,
            )
            response.raise_for_status()
            result = response.json()

            transformed = result["choices"][0]["message"]["content"]

            print(f"\n转换后:\n{transformed}")
            print(f"\n{'='*60}\n")

            return transformed

        except Exception as e:
            print(f"\n❌ 测试失败: {e}\n")
            return None


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="测试风格迁移 LoRA")
    parser.add_argument("--text", type=str,
                        default="夜色渐深，街道上的行人越来越少，只剩下远处几盏昏黄的灯光在风中摇曳。一个黑衣人从巷子里走出来，他的脚步很轻，几乎没有声音。",
                        help="测试文本")
    parser.add_argument("--style", type=str, default="古龙",
                        help="风格名称")
    parser.add_argument("--lora", type=str, default="gulong-style-lora",
                        help="LoRA 适配器名称")
    parser.add_argument("--vllm-url", type=str, default="http://localhost:8000",
                        help="vLLM 服务地址")
    parser.add_argument("--compare", action="store_true",
                        help="对比所有风格")
    parser.add_argument("--baseline", action="store_true",
                        help="同时测试基线模型（无 LoRA）")

    args = parser.parse_args()

    if args.compare:
        # 对比多个风格
        asyncio.run(compare_styles(args.text, args.vllm_url))
    else:
        # 单个风格测试
        if args.baseline:
            # 先测试基线
            asyncio.run(test_with_base_model(args.text, args.style, args.vllm_url))

        # 测试 LoRA
        asyncio.run(test_style_transfer(
            args.text,
            args.style,
            args.lora,
            args.vllm_url
        ))
