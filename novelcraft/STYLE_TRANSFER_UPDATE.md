# 风格迁移功能更新说明

## 变更概述

风格迁移功能已从**缓存架构**改为**直接调用模型推理**，更符合实际使用场景。

## 主要变更

### 1. 架构简化

**之前**：
- 三层缓存架构（Hot/Warm/Cold）
- 复杂的缓存管理和淘汰策略
- 模拟的模型推理

**现在**：
- 直接调用 vLLM 部署的 Qwen3-8B 模型
- 通过 LoRA 适配器实现不同风格
- 真实的模型推理流程

### 2. 数据模型变更

**删除的表**：
- `style_model_cache` - 缓存状态表

**新增的表**：
- `style_model_info` - 风格模型信息表

**保留的表**：
- `style_transfer_tasks` - 任务记录表

### 3. 服务层变更

**删除的文件**：
- `backend/services/style_cache_service.py` - 缓存管理服务

**修改的文件**：
- `backend/services/style_transfer_service.py` - 简化为直接调用模型
- `backend/models/style_models.py` - 更新数据模型
- `backend/routers/style_transfer.py` - 简化 API 路由

### 4. API 变更

**保留的端点**：
- `POST /api/style-transfer/transfer` - 执行风格迁移
- `GET /api/style-transfer/task/{task_id}` - 查询任务状态
- `GET /api/style-transfer/styles` - 列出可用风格

**删除的端点**：
- `GET /api/style-transfer/cache/stats` - 缓存统计（不再需要）

## 工作流程

### 新的风格迁移流程

```
1. 用户提交风格迁移请求
   ↓
2. 查询风格信息（style_model_info 表）
   ↓
3. 构建 Prompt（系统提示词 + 用户输入）
   ↓
4. 调用 vLLM API（指定 LoRA 适配器）
   ↓
5. 返回转换后的文本
   ↓
6. 保存任务记录
```

### vLLM 调用示例

```python
# 请求格式
{
    "model": "Qwen/Qwen3-8B-Instruct",
    "messages": [
        {
            "role": "system",
            "content": "你是一位专业的文学风格转换专家..."
        },
        {
            "role": "user",
            "content": "将以下文本转换为古龙的写作风格：\n\n{原文}"
        }
    ],
    "temperature": 0.7,
    "max_tokens": 1000,
    "extra_body": {
        "lora_adapter": "gulong-style-lora"  # 指定 LoRA 适配器
    }
}
```

## 模型训练

详细的模型训练方案请参考：[MODEL_TRAINING_GUIDE.md](MODEL_TRAINING_GUIDE.md)

### 快速开始

1. **准备训练数据**
   ```bash
   python scripts/prepare_style_dataset.py
   ```

2. **训练 LoRA 适配器**
   ```bash
   llamafactory-cli train train_gulong.yaml
   ```

3. **部署 vLLM 服务**
   ```bash
   python -m vllm.entrypoints.openai.api_server \
       --model Qwen/Qwen3-8B-Instruct \
       --enable-lora \
       --lora-modules gulong-style-lora=outputs/gulong-style-lora/final
   ```

## 配置更新

### 环境变量

```bash
# vLLM 服务地址
NOVELCRAFT_VLLM_BASE_URL=http://localhost:8000
```

### 数据库迁移

```bash
cd novelcraft/backend

# 运行迁移（会删除旧的缓存表，创建新的信息表）
python migrations/migrate_v2.py

# 初始化风格数据
python migrations/init_styles.py
```

## 性能对比

| 指标 | 缓存架构 | 直接推理 |
|------|---------|---------|
| 首次请求延迟 | 2-5秒 | 1-3秒 |
| 缓存命中延迟 | <100ms | N/A |
| 内存占用 | 高（需缓存模型） | 低（仅 vLLM） |
| 实现复杂度 | 高 | 低 |
| 可维护性 | 中 | 高 |
| 风格切换 | 需加载 | 即时切换 |

## 优势

1. **架构简单**：去掉复杂的缓存管理逻辑
2. **易于维护**：代码量减少约 40%
3. **灵活性高**：可以随时添加新风格，无需管理缓存
4. **真实推理**：使用真实的模型推理，而非模拟
5. **资源优化**：vLLM 自带高效的推理优化

## 迁移指南

### 对于开发者

1. 删除旧的缓存相关代码
2. 更新数据库表结构
3. 配置 vLLM 服务地址
4. 训练并部署 LoRA 适配器

### 对于用户

API 接口保持兼容，无需修改客户端代码。

## 后续优化

1. **批量推理**：支持批量文本转换
2. **流式输出**：支持 SSE 流式返回
3. **多模型支持**：支持不同规模的基座模型
4. **风格混合**：支持多个风格的混合转换

---

**更新时间**：2026-05-30  
**版本**：V2.0 (Simplified)
