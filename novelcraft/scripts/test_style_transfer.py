#!/usr/bin/env python3
"""
风格迁移功能测试脚本

测试直接调用 vLLM 模型的风格迁移功能
"""
import asyncio
import httpx
from datetime import datetime


# 配置
BACKEND_URL = "http://localhost:8000"
VLLM_URL = "http://localhost:8000"  # vLLM 服务地址


async def test_vllm_direct():
    """测试直接调用 vLLM API"""
    print("\n" + "="*60)
    print("测试 1: 直接调用 vLLM API")
    print("="*60)

    test_text = "夜色降临，一个黑衣人走进了客栈。他坐在角落里，默默地喝着酒。"

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                f"{VLLM_URL}/v1/chat/completions",
                json={
                    "model": "Qwen/Qwen3-8B-Instruct",
                    "messages": [
                        {
                            "role": "system",
                            "content": "你是一位专业的文学风格转换专家，擅长将文本转换为古龙的写作风格。"
                        },
                        {
                            "role": "user",
                            "content": f"将以下文本转换为古龙的写作风格：\n\n{test_text}"
                        }
                    ],
                    "temperature": 0.7,
                    "max_tokens": 500,
                    "extra_body": {
                        "lora_adapter": "gulong-style-lora"
                    }
                }
            )

            if response.status_code == 200:
                result = response.json()
                transformed = result["choices"][0]["message"]["content"]
                print(f"\n✓ vLLM 调用成功")
                print(f"\n原文:\n{test_text}")
                print(f"\n转换后:\n{transformed}")
            else:
                print(f"\n✗ vLLM 调用失败: HTTP {response.status_code}")
                print(f"响应: {response.text}")

        except httpx.ConnectError:
            print(f"\n✗ 无法连接到 vLLM 服务 ({VLLM_URL})")
            print("请确保 vLLM 服务已启动")
        except Exception as e:
            print(f"\n✗ 错误: {e}")


async def test_backend_api():
    """测试后端风格迁移 API"""
    print("\n" + "="*60)
    print("测试 2: 后端风格迁移 API")
    print("="*60)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 获取可用风格列表
        print("\n2.1 获取可用风格列表...")
        try:
            response = await client.get(f"{BACKEND_URL}/api/style-transfer/styles")
            if response.status_code == 200:
                styles = response.json()["styles"]
                print(f"✓ 找到 {len(styles)} 个可用风格:")
                for style in styles:
                    print(f"  - {style['style_name']} ({style['style_id']})")
                    print(f"    描述: {style['description'][:50]}...")
            else:
                print(f"✗ 失败: HTTP {response.status_code}")
        except httpx.ConnectError:
            print(f"✗ 无法连接到后端服务 ({BACKEND_URL})")
            print("请确保后端服务已启动")
            return
        except Exception as e:
            print(f"✗ 错误: {e}")
            return

        # 2. 执行风格迁移
        print("\n2.2 执行风格迁移（古龙风格）...")
        test_cases = [
            {
                "text": "夜色降临，一个黑衣人走进了客栈。他坐在角落里，默默地喝着酒。",
                "style": "gulong"
            },
            {
                "text": "太阳升起来了，照在田野上，小鸟在树上唱歌。",
                "style": "caowenxuan"
            },
            {
                "text": "他拔出了剑，准备与敌人决一死战。",
                "style": "jinyong"
            }
        ]

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n测试用例 {i}: {test_case['style']} 风格")
            try:
                response = await client.post(
                    f"{BACKEND_URL}/api/style-transfer/transfer",
                    json={
                        "original_text": test_case["text"],
                        "style_id": test_case["style"],
                        "project_id": "test-project"
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if result["status"] == "completed":
                        print(f"✓ 转换成功 (耗时: {result['inference_time_ms']}ms)")
                        print(f"\n原文:\n{result['original_text']}")
                        print(f"\n转换后:\n{result['transformed_text']}")
                    else:
                        print(f"✗ 转换失败: {result.get('error', '未知错误')}")
                else:
                    print(f"✗ 请求失败: HTTP {response.status_code}")

            except Exception as e:
                print(f"✗ 错误: {e}")

            # 等待一下，避免请求过快
            await asyncio.sleep(1)


async def test_performance():
    """测试性能"""
    print("\n" + "="*60)
    print("测试 3: 性能测试")
    print("="*60)

    test_text = "夜色降临，一个黑衣人走进了客栈。" * 10  # 较长文本
    num_requests = 5

    print(f"\n执行 {num_requests} 次风格迁移请求...")

    async with httpx.AsyncClient(timeout=60.0) as client:
        times = []

        for i in range(num_requests):
            start = datetime.now()

            try:
                response = await client.post(
                    f"{BACKEND_URL}/api/style-transfer/transfer",
                    json={
                        "original_text": test_text,
                        "style_id": "gulong",
                        "project_id": "test-project"
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if result["status"] == "completed":
                        elapsed = (datetime.now() - start).total_seconds() * 1000
                        times.append(elapsed)
                        print(f"  请求 {i+1}: {elapsed:.0f}ms")

            except Exception as e:
                print(f"  请求 {i+1}: 失败 - {e}")

        if times:
            print(f"\n性能统计:")
            print(f"  平均耗时: {sum(times)/len(times):.0f}ms")
            print(f"  最快: {min(times):.0f}ms")
            print(f"  最慢: {max(times):.0f}ms")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("NovelCraft 风格迁移功能测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    # 测试 1: 直接调用 vLLM
    await test_vllm_direct()

    # 测试 2: 后端 API
    await test_backend_api()

    # 测试 3: 性能测试
    await test_performance()

    print("\n" + "="*60)
    print("测试完成！")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(main())
