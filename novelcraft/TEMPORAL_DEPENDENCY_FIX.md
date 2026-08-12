# Temporal 工作流依赖问题说明

## 问题描述

```python
ModuleNotFoundError: No module named 'temporalio'
```

## 问题原因

Temporal 工作流功能需要 `temporalio` 包，但该包可能未安装。

## 解决方案

### 方案一：安装 Temporal 依赖（推荐用于生产环境）

```bash
# 安装 temporalio
pip install temporalio==1.7.1

# 或者安装所有依赖
cd novelcraft/backend
pip install -r requirements.txt
```

### 方案二：禁用 Temporal 功能（快速开发）

如果暂时不需要工作流功能，可以注释掉相关导入：

#### 1. 修改 `main.py`

```python
# 注释掉 Temporal 相关导入
# from backend.services.temporal_service import temporal_service

# 注释掉 Temporal 初始化
# try:
#     await temporal_service.init_client()
#     logger.info("Temporal 工作流服务已初始化")
# except Exception as e:
#     logger.warning("Temporal 工作流服务初始化失败: %s", e)
```

#### 2. 修改 `routers/__init__.py`（如果有）

```python
# 注释掉工作流路由
# from backend.routers import workflows
# app.include_router(workflows.router)
```

### 方案三：条件导入（推荐）

修改相关文件，使 Temporal 成为可选依赖：

```python
# backend/main.py
try:
    from backend.services.temporal_service import temporal_service
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    logger.warning("Temporal 未安装，工作流功能将不可用")

# 在 lifespan 中条件初始化
if TEMPORAL_AVAILABLE:
    try:
        await temporal_service.init_client()
        logger.info("Temporal 工作流服务已初始化")
    except Exception as e:
        logger.warning("Temporal 工作流服务初始化失败: %s", e)
```

## 快速修复脚本

创建 `fix_temporal.py`：

```python
#!/usr/bin/env python3
"""
修复 Temporal 依赖问题
"""
import subprocess
import sys

def install_temporal():
    """安装 Temporal 依赖"""
    print("正在安装 temporalio...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "temporalio==1.7.1"])
        print("✓ temporalio 安装成功")
        return True
    except subprocess.CalledProcessError:
        print("✗ temporalio 安装失败")
        return False

def check_temporal():
    """检查 Temporal 是否已安装"""
    try:
        import temporalio
        print(f"✓ temporalio 已安装 (版本: {temporalio.__version__})")
        return True
    except ImportError:
        print("✗ temporalio 未安装")
        return False

if __name__ == "__main__":
    if not check_temporal():
        install_temporal()
        check_temporal()
```

运行：
```bash
python fix_temporal.py
```

## 功能影响

如果不安装 Temporal：

### 可用功能 ✅
- 风格迁移
- 实时协同编辑
- 项目管理
- 大纲规划
- 人物管理

### 不可用功能 ❌
- 整书创作工作流
- 章节修订工作流
- 长时间任务编排

## 推荐做法

### 开发环境
```bash
# 安装核心依赖（不含 Temporal）
pip install fastapi uvicorn sqlalchemy asyncpg redis

# 需要时再安装 Temporal
pip install temporalio
```

### 生产环境
```bash
# 安装所有依赖
pip install -r requirements.txt
```

## 验证安装

```bash
# 检查是否安装成功
python -c "import temporalio; print(f'Temporal 版本: {temporalio.__version__}')"

# 启动后端
uvicorn backend.main:app --reload
```

---

**修复时间**: 2026-05-30  
**状态**: ✅ 已提供多种解决方案
