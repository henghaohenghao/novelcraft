# 导入错误修复说明

## 问题描述

```python
ImportError: cannot import name 'get_async_session' from 'backend.models.database'
```

## 问题原因

在 `backend/models/database.py` 中，数据库会话函数名为 `get_db`，但在其他文件中导入时使用的是 `get_async_session`：

**database.py 中的定义**：
```python
async def get_db() -> AsyncSession:
    ...
```

**其他文件中的导入**：
```python
from backend.models.database import get_async_session  # ❌ 错误
```

## 解决方案

在 `database.py` 中添加别名，保持向后兼容：

```python
async def get_db() -> AsyncSession:
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


# 别名，保持兼容性
get_async_session = get_db
```

## 影响的文件

以下文件使用了 `get_async_session`：

1. `backend/routers/style_transfer.py`
2. `backend/routers/collaboration.py`
3. `backend/migrations/init_styles.py`

## 修复状态

✅ **已修复**

- 文件：`novelcraft/backend/models/database.py`
- 提交：已添加 `get_async_session` 别名
- 状态：所有导入错误已解决

## 验证

现在可以正常导入：

```python
from backend.models.database import get_async_session  # ✅ 正确
from backend.models.database import get_db  # ✅ 也可以
```

两个名称都指向同一个函数，保持了兼容性。

---

**修复时间**: 2026-05-30  
**Git 提交**: fix: add get_async_session alias for database session
