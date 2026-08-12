
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
import sys

print("=" * 60)
print("开始测试 Qdrant 连接")
print("=" * 60)
print()

# 配置
host = "localhost"
port = 6333
api_key = ""

print(f"连接参数:")
print(f"  - HOST: {host}")
print(f"  - PORT: {port}")
print()

# 测试连接
print("正在连接 Qdrant...")
try:
    client = QdrantClient(
        host=host,
        port=port,
        api_key=api_key if api_key else None,
        timeout=5
    )
    print("✅ 连接成功!")
    print()

    # 获取集合列表
    print("获取集合列表...")
    collections = client.get_collections()
    print(f"✅ 当前集合数量: {len(collections.collections)}")
    if collections.collections:
        print("  集合列表:")
        for col in collections.collections:
            print(f"    - {col.name}")
    else:
        print("  (暂无集合)")
    print()

    # 测试创建集合（如果不存在）
    test_collection_name = "test_connection"
    print(f"测试集合操作...")
    if client.collection_exists(test_collection_name):
        print(f"  测试集合已存在，删除...")
        client.delete_collection(test_collection_name)
    
    print(f"  创建测试集合...")
    client.create_collection(
        collection_name=test_collection_name,
        vectors_config=VectorParams(size=128, distance=Distance.COSINE)
    )
    print(f"  ✅ 创建成功")
    
    print(f"  清理测试集合...")
    client.delete_collection(test_collection_name)
    print(f"  ✅ 删除成功")
    print()

    print("=" * 60)
    print("🎉 所有测试通过! Qdrant 运行正常!")
    print("=" * 60)
    print()
    print("现在可以启动 NovelCraft 后端了!")

except Exception as e:
    print(f"❌ 连接失败:")
    print(f"   {type(e).__name__}: {e}")
    print()
    print("=" * 60)
    print("💡 请检查:")
    print("  1. Qdrant 是否已启动?")
    print("  2. Qdrant 是否在端口 6333 上运行?")
    print("  3. 防火墙是否阻止了连接?")
    print("=" * 60)
    import traceback
    print("\n详细错误信息:")
    traceback.print_exc()
    sys.exit(1)

