#!/usr/bin/env python3
"""
快速验证脚本 - 检查所有模块是否可以正常导入
"""
import sys
import importlib.util

def check_import(module_path, module_name):
    """检查模块是否可以导入"""
    try:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            print(f"✓ {module_name}")
            return True
    except Exception as e:
        print(f"✗ {module_name}: {e}")
        return False

print("="*60)
print("NovelCraft V2.0 模块导入验证")
print("="*60)

modules = [
    ("novelcraft/backend/models/style_models.py", "style_models"),
    ("novelcraft/backend/models/collaboration_models.py", "collaboration_models"),
    ("novelcraft/backend/services/style_cache_service.py", "style_cache_service"),
    ("novelcraft/backend/services/style_transfer_service.py", "style_transfer_service"),
    ("novelcraft/backend/services/collaboration_service.py", "collaboration_service"),
    ("novelcraft/backend/services/temporal_service.py", "temporal_service"),
]

success_count = 0
for path, name in modules:
    if check_import(path, name):
        success_count += 1

print("="*60)
print(f"结果: {success_count}/{len(modules)} 模块导入成功")
print("="*60)

sys.exit(0 if success_count == len(modules) else 1)
