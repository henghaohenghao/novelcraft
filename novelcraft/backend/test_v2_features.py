"""
V2.0 功能测试脚本

测试三个核心功能：
1. 风格迁移模型缓存
2. 实时协同编辑
3. Temporal 工作流
"""
import asyncio
import httpx
from datetime import datetime


BASE_URL = "http://localhost:8000"


async def test_style_transfer():
    """测试风格迁移功能"""
    print("\n" + "="*50)
    print("测试 1: 风格迁移模型缓存")
    print("="*50)

    async with httpx.AsyncClient() as client:
        # 1. 获取可用风格列表
        print("\n1.1 获取可用风格列表...")
        response = await client.get(f"{BASE_URL}/api/style-transfer/styles")
        if response.status_code == 200:
            styles = response.json()["styles"]
            print(f"✓ 找到 {len(styles)} 个可用风格:")
            for style in styles[:3]:
                print(f"  - {style['style_name']} ({style['style_id']})")
        else:
            print(f"✗ 失败: {response.status_code}")

        # 2. 执行风格迁移
        print("\n1.2 执行风格迁移...")
        transfer_request = {
            "original_text": "夜色如墨，月光洒在青石板路上。",
            "style_id": "gulong",
            "project_id": "test-project-001",
        }
        response = await client.post(
            f"{BASE_URL}/api/style-transfer/transfer",
            json=transfer_request,
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 转换成功:")
            print(f"  任务ID: {result['task_id']}")
            print(f"  原文: {result['original_text']}")
            print(f"  转换后: {result['transformed_text']}")
            print(f"  耗时: {result['inference_time_ms']}ms")
            print(f"  缓存命中: {result['cache_hit']}")
        else:
            print(f"✗ 失败: {response.status_code}")

        # 3. 再次执行相同风格（测试缓存命中）
        print("\n1.3 再次执行相同风格（测试缓存）...")
        response = await client.post(
            f"{BASE_URL}/api/style-transfer/transfer",
            json=transfer_request,
        )
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 转换成功:")
            print(f"  缓存命中: {result['cache_hit']} (应该为 True)")
            print(f"  耗时: {result['inference_time_ms']}ms")
        else:
            print(f"✗ 失败: {response.status_code}")

        # 4. 查看缓存统计
        print("\n1.4 查看缓存统计...")
        response = await client.get(f"{BASE_URL}/api/style-transfer/cache/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ 缓存统计:")
            print(f"  Hot Cache: {stats['hot_cache']['size']} 个模型, "
                  f"{stats['hot_cache']['usage_mb']}MB / {stats['hot_cache']['capacity_mb']}MB")
            print(f"  Warm Cache: {stats['warm_cache']['size']} 个模型, "
                  f"{stats['warm_cache']['usage_mb']}MB / {stats['warm_cache']['capacity_mb']}MB")
            print(f"  总请求: {stats['stats']['total_requests']}")
            print(f"  命中率: {stats['stats']['hit_rate']}%")
        else:
            print(f"✗ 失败: {response.status_code}")


async def test_collaboration():
    """测试实时协同编辑功能"""
    print("\n" + "="*50)
    print("测试 2: 实时协同编辑")
    print("="*50)

    async with httpx.AsyncClient() as client:
        # 1. 创建协同编辑房间
        print("\n2.1 创建协同编辑房间...")
        response = await client.post(
            f"{BASE_URL}/api/collaboration/rooms",
            params={
                "chapter_id": "chapter-001",
                "room_name": "第一章协同编辑",
            },
        )
        if response.status_code == 200:
            room = response.json()
            room_id = room["room_id"]
            print(f"✓ 房间创建成功:")
            print(f"  房间ID: {room_id}")
            print(f"  章节ID: {room['chapter_id']}")
            print(f"  房间名: {room['room_name']}")

            # 2. 获取房间用户列表
            print("\n2.2 获取房间用户列表...")
            response = await client.get(
                f"{BASE_URL}/api/collaboration/rooms/{room_id}/users"
            )
            if response.status_code == 200:
                users = response.json()["users"]
                print(f"✓ 当前在线用户: {len(users)} 人")
            else:
                print(f"✗ 失败: {response.status_code}")

            print("\n提示: WebSocket 连接需要使用 WebSocket 客户端测试")
            print(f"  连接地址: ws://localhost:8000/api/collaboration/ws/{room_id}")
            print(f"  参数: user_id=test-user&user_name=测试用户&connection_id=conn-001")

        else:
            print(f"✗ 失败: {response.status_code}")


async def test_workflows():
    """测试 Temporal 工作流功能"""
    print("\n" + "="*50)
    print("测试 3: Temporal 工作流")
    print("="*50)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. 启动整书创作工作流
        print("\n3.1 启动整书创作工作流...")
        workflow_request = {
            "project_id": "test-project-002",
            "title": "测试小说",
            "synopsis": "这是一个测试小说的梗概...",
            "genre": "玄幻",
            "style": "古龙",
            "chapter_count": 3,
            "user_id": "test-user-001",
        }
        response = await client.post(
            f"{BASE_URL}/api/workflows/book-creation",
            json=workflow_request,
        )
        if response.status_code == 200:
            result = response.json()
            workflow_id = result["workflow_id"]
            print(f"✓ 工作流启动成功:")
            print(f"  工作流ID: {workflow_id}")
            print(f"  状态: {result['status']}")
            print(f"  消息: {result['message']}")

            # 2. 查询工作流状态
            print("\n3.2 查询工作流状态...")
            await asyncio.sleep(2)  # 等待一会儿
            response = await client.get(
                f"{BASE_URL}/api/workflows/status/{workflow_id}"
            )
            if response.status_code == 200:
                status = response.json()
                print(f"✓ 工作流状态:")
                print(f"  状态: {status['status']}")
                print(f"  开始时间: {status.get('start_time', 'N/A')}")
            else:
                print(f"✗ 失败: {response.status_code}")

            print("\n提示: 工作流执行需要 Temporal Worker 运行")
            print("  启动命令: python -m backend.workflows.worker")

        else:
            print(f"✗ 失败: {response.status_code}")


async def test_health():
    """测试健康检查"""
    print("\n" + "="*50)
    print("健康检查")
    print("="*50)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/health")
        if response.status_code == 200:
            health = response.json()
            print(f"\n✓ 系统状态: {health['status']}")
            print(f"  版本: {health['version']}")
            print(f"\n服务状态:")
            for service, status in health['services'].items():
                status_icon = "✓" if status else "✗"
                print(f"  {status_icon} {service}: {status}")
            print(f"\n功能状态:")
            for feature, enabled in health['features'].items():
                status_icon = "✓" if enabled else "✗"
                print(f"  {status_icon} {feature}: {enabled}")
        else:
            print(f"✗ 健康检查失败: {response.status_code}")


async def main():
    """运行所有测试"""
    print("\n" + "="*60)
    print("NovelCraft V2.0 功能测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    try:
        # 健康检查
        await test_health()

        # 测试风格迁移
        await test_style_transfer()

        # 测试协同编辑
        await test_collaboration()

        # 测试工作流
        await test_workflows()

        print("\n" + "="*60)
        print("测试完成！")
        print("="*60)

    except httpx.ConnectError:
        print("\n✗ 错误: 无法连接到后端服务")
        print("  请确保后端服务已启动: uvicorn backend.main:app --reload")
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
