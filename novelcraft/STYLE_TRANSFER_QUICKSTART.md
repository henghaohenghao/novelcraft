# 风格迁移功能完整指南

## 快速开始

### 1. 训练模型

```bash
# 训练所有风格的 LoRA 适配器
cd novelcraft
bash scripts/train_all_styles.sh
```

### 2. 部署 vLLM 服务

```bash
# 启动 vLLM 服务，加载所有 LoRA 适配器
bash scripts/deploy_vllm.sh
```

### 3. 启动后端服务

```bash
# 运行数据库迁移
cd backend
python migrations/migrate_v2.py
python migrations/init_styles.py

# 启动 FastAPI 服务
uvicorn backend.main:app --reload
```

### 4. 测试功能

```bash
# 运行测试脚本
python scripts/test_style_transfer.py
```

## 目录结构

```
novelcraft/
├── scripts/
│   ├── train_style_model.py      # 单个风格训练脚本
│   ├── train_all_styles.sh       # 批量训练脚本
│   ├── deploy_vllm.sh            # vLLM 部署脚本
│   └── test_style_transfer.py    # 测试脚本
├── data/
│   └── style_transfer/           # 训练数据
│       ├── gulong_train.json
│       ├── caowenxuan_train.json
│       └── ...
├── outputs/                      # 训练输出
│   ├── gulong-style-lora/
│   ├── caowenxuan-style-lora/
│   └── ...
└── MODEL_TRAINING_GUIDE.md       # 详细训练指南
```

## API 使用

### 执行风格迁移

```bash
curl -X POST http://localhost:8000/api/style-transfer/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "original_text": "夜色降临，一个黑衣人走进了客栈。",
    "style_id": "gulong",
    "project_id": "my-novel"
  }'
```

### 查询可用风格

```bash
curl http://localhost:8000/api/style-transfer/styles
```

### 查询任务状态

```bash
curl http://localhost:8000/api/style-transfer/task/{task_id}
```

## 支持的风格

| 风格ID | 风格名称 | 特点 |
|--------|---------|------|
| gulong | 古龙 | 短句、留白、节奏感强 |
| caowenxuan | 曹文轩 | 诗意、细腻、温暖 |
| jinyong | 金庸 | 武侠、历史、人物丰满 |
| liubixin | 刘慈欣 | 科幻、理性、宏大 |
| wangxiaobo | 王小波 | 幽默、讽刺、思辨 |
| luxun | 鲁迅 | 批判、深刻、简洁 |

## 常见问题

### Q: 训练需要多长时间？
A: 单个风格约 1-2 小时（使用 A100 GPU）

### Q: 需要多少训练数据？
A: 建议每个风格至少 500 个样本，推荐 1500+ 个

### Q: 如何添加新风格？
A: 
1. 准备训练数据
2. 运行 `python scripts/train_style_model.py --style-name "新风格" --style-id "new_style"`
3. 重启 vLLM 服务

### Q: 推理速度如何？
A: 通常 1-3 秒（取决于文本长度和 GPU 性能）

## 更多文档

- [详细训练指南](MODEL_TRAINING_GUIDE.md)
- [功能更新说明](STYLE_TRANSFER_UPDATE.md)
- [项目报告](PROJECT_REPORT.md)
