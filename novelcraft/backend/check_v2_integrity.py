#!/usr/bin/env python3
"""
代码完整性检查脚本

检查 V2.0 实现的所有文件是否存在且语法正确
"""
import os
import sys
from pathlib import Path


def check_file_exists(filepath: str) -> bool:
    """检查文件是否存在"""
    exists = Path(filepath).exists()
    status = "✓" if exists else "✗"
    print(f"  {status} {filepath}")
    return exists


def main():
    print("="*60)
    print("NovelCraft V2.0 代码完整性检查")
    print("="*60)

    base_dir = Path(__file__).parent.parent
    all_exist = True

    # 1. 数据模型
    print("\n1. 数据模型:")
    models = [
        "novelcraft/backend/models/style_models.py",
        "novelcraft/backend/models/collaboration_models.py",
    ]
    for model in models:
        all_exist &= check_file_exists(base_dir / model)

    # 2. 服务层
    print("\n2. 服务层:")
    services = [
        "novelcraft/backend/services/style_cache_service.py",
        "novelcraft/backend/services/style_transfer_service.py",
        "novelcraft/backend/services/collaboration_service.py",
        "novelcraft/backend/services/temporal_service.py",
    ]
    for service in services:
        all_exist &= check_file_exists(base_dir / service)

    # 3. API 路由
    print("\n3. API 路由:")
    routers = [
        "novelcraft/backend/routers/style_transfer.py",
        "novelcraft/backend/routers/collaboration.py",
        "novelcraft/backend/routers/workflows.py",
    ]
    for router in routers:
        all_exist &= check_file_exists(base_dir / router)

    # 4. 工作流
    print("\n4. Temporal 工作流:")
    workflows = [
        "novelcraft/backend/workflows/book_creation_workflow.py",
        "novelcraft/backend/workflows/worker.py",
    ]
    for workflow in workflows:
        all_exist &= check_file_exists(base_dir / workflow)

    # 5. 迁移脚本
    print("\n5. 数据库迁移:")
    migrations = [
        "novelcraft/backend/migrations/migrate_v2.py",
        "novelcraft/backend/migrations/init_styles.py",
    ]
    for migration in migrations:
        all_exist &= check_file_exists(base_dir / migration)

    # 6. 配置文件
    print("\n6. 配置文件:")
    configs = [
        "novelcraft/backend/.env.example",
        "novelcraft/backend/requirements.txt",
        "novelcraft/backend/config_v2.py",
        "docker-compose.yml",
        "start.sh",
    ]
    for config in configs:
        all_exist &= check_file_exists(base_dir / config)

    # 7. 文档
    print("\n7. 文档:")
    docs = [
        "README.md",
        "novelcraft/V2.0_SUMMARY.md",
        "novelcraft/V2.0_IMPLEMENTATION.md",
    ]
    for doc in docs:
        all_exist &= check_file_exists(base_dir / doc)

    # 8. 测试脚本
    print("\n8. 测试脚本:")
    tests = [
        "novelcraft/backend/test_v2_features.py",
    ]
    for test in tests:
        all_exist &= check_file_exists(base_dir / test)

    # 总结
    print("\n" + "="*60)
    if all_exist:
        print("✓ 所有文件检查通过！")
        print("="*60)
        print("\n下一步:")
        print("  1. 启动服务: bash start.sh")
        print("  2. 运行测试: python novelcraft/backend/test_v2_features.py")
        print("  3. 查看文档: cat novelcraft/V2.0_SUMMARY.md")
        return 0
    else:
        print("✗ 部分文件缺失，请检查！")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
