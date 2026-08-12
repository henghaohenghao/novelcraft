#!/bin/bash

# NovelCraft V2.0 完整部署脚本

set -e

echo "=========================================="
echo "NovelCraft V2.0 完整部署"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 检查 Docker
echo -e "${YELLOW}[1/8] 检查 Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}错误: Docker 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker 已安装${NC}"

# 检查 Docker Compose
echo -e "${YELLOW}[2/8] 检查 Docker Compose...${NC}"
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}错误: Docker Compose 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose 已安装${NC}"

# 检查 Python
echo -e "${YELLOW}[3/8] 检查 Python...${NC}"
if ! command -v python &> /dev/null; then
    echo -e "${RED}错误: Python 未安装${NC}"
    exit 1
fi
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${GREEN}✓ Python ${PYTHON_VERSION} 已安装${NC}"

# 启动基础设施服务
echo ""
echo -e "${YELLOW}[4/8] 启动基础设施服务...${NC}"
docker-compose up -d postgres neo4j qdrant redis temporal minio
echo -e "${GREEN}✓ 基础设施服务已启动${NC}"

# 等待服务就绪
echo ""
echo -e "${YELLOW}[5/8] 等待服务就绪...${NC}"
sleep 15
echo -e "${GREEN}✓ 服务已就绪${NC}"

# 运行数据库迁移
echo ""
echo -e "${YELLOW}[6/8] 运行数据库迁移...${NC}"
cd novelcraft/backend
python migrations/migrate_v2.py
echo -e "${GREEN}✓ 数据库迁移完成${NC}"

# 初始化风格模型
echo ""
echo -e "${YELLOW}[7/8] 初始化风格模型数据...${NC}"
python migrations/init_styles.py
echo -e "${GREEN}✓ 风格模型初始化完成${NC}"

# 返回根目录
cd ../..

# 启动应用服务
echo ""
echo -e "${YELLOW}[8/8] 启动应用服务...${NC}"
docker-compose up -d backend temporal-worker celery-worker frontend
echo -e "${GREEN}✓ 应用服务已启动${NC}"

# 等待应用启动
echo ""
echo "等待应用启动..."
sleep 10

# 健康检查
echo ""
echo -e "${YELLOW}执行健康检查...${NC}"
HEALTH_CHECK=$(curl -s http://localhost:8000/api/health || echo "failed")
if [[ $HEALTH_CHECK == *"ok"* ]]; then
    echo -e "${GREEN}✓ 健康检查通过${NC}"
else
    echo -e "${RED}✗ 健康检查失败${NC}"
    echo "请检查日志: docker-compose logs backend"
fi

# 显示服务状态
echo ""
echo "=========================================="
echo -e "${GREEN}NovelCraft V2.0 部署完成！${NC}"
echo "=========================================="
echo ""
echo "服务地址："
echo "  - 前端:        http://localhost:3000"
echo "  - 后端 API:    http://localhost:8000"
echo "  - API 文档:    http://localhost:8000/docs"
echo "  - Temporal UI: http://localhost:8233"
echo "  - Neo4j:       http://localhost:7474"
echo "  - MinIO:       http://localhost:9001"
echo ""
echo "验证命令："
echo "  curl http://localhost:8000/api/health"
echo ""
echo "运行测试："
echo "  python novelcraft/backend/test_v2_features.py"
echo ""
echo "查看日志："
echo "  docker-compose logs -f backend"
echo ""
echo "停止服务："
echo "  docker-compose down"
echo ""
echo "查看部署清单："
echo "  cat DEPLOYMENT_CHECKLIST.md"
echo ""
