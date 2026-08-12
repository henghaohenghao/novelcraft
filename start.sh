#!/bin/bash

# NovelCraft V2.0 快速启动脚本

set -e

echo "=========================================="
echo "NovelCraft V2.0 快速启动"
echo "=========================================="

# 检查 Docker 是否运行
if ! docker info > /dev/null 2>&1; then
    echo "错误: Docker 未运行，请先启动 Docker"
    exit 1
fi

# 启动基础设施
echo ""
echo "1. 启动基础设施服务..."
docker-compose up -d postgres neo4j qdrant redis temporal minio

# 等待服务就绪
echo ""
echo "2. 等待服务就绪..."
sleep 10

# 检查服务状态
echo ""
echo "3. 检查服务状态..."
docker-compose ps

# 运行数据库迁移
echo ""
echo "4. 运行数据库迁移..."
cd novelcraft/backend
python migrations/migrate_v2.py

# 初始化风格模型
echo ""
echo "5. 初始化风格模型数据..."
python migrations/init_styles.py

# 返回根目录
cd ../..

# 启动应用服务
echo ""
echo "6. 启动应用服务..."
docker-compose up -d backend temporal-worker celery-worker frontend

echo ""
echo "=========================================="
echo "NovelCraft V2.0 启动完成！"
echo "=========================================="
echo ""
echo "服务地址："
echo "  - 前端: http://localhost:3000"
echo "  - 后端 API: http://localhost:8000"
echo "  - API 文档: http://localhost:8000/docs"
echo "  - Temporal UI: http://localhost:8233"
echo "  - Neo4j Browser: http://localhost:7474"
echo "  - MinIO Console: http://localhost:9001"
echo ""
echo "健康检查："
echo "  curl http://localhost:8000/api/health"
echo ""
echo "查看日志："
echo "  docker-compose logs -f backend"
echo ""
echo "停止服务："
echo "  docker-compose down"
echo ""
