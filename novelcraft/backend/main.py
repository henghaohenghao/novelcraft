import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.models.database import init_db
from backend.routers import projects, outlines, writing, characters, style_transfer, collaboration, workflows, auth
from backend.services.neo4j_service import neo4j_service
from backend.services.qdrant_service import qdrant_service
from backend.services.collaboration_service import collaboration_service

settings = get_settings()
logger = logging.getLogger("novelcraft")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# Temporal 工作流服务（可选依赖）
try:
    from backend.services.temporal_service import temporal_service
    TEMPORAL_AVAILABLE = True
except ImportError:
    TEMPORAL_AVAILABLE = False
    logger.warning("Temporal 未安装，工作流功能将不可用。安装命令: pip install temporalio")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("数据库已初始化 (driver=%s)", settings.db_driver)

    try:
        neo4j_service.init_constraints()
        logger.info("Neo4j 已连接 (uri=%s)", settings.neo4j_uri)
    except Exception as e:
        logger.warning("Neo4j 不可用，关系图谱功能降级: %s", e)

    try:
        from backend.services.embedding_service import embedding_service
        dim = embedding_service.dimension
        qdrant_service.init_collections(embedding_dim=dim)
        logger.info("Qdrant 已连接 (host=%s:%s, dim=%s)", settings.qdrant_host, settings.qdrant_port, dim)
    except Exception as e:
        logger.warning("Qdrant 或 embedding 模型不可用，向量检索功能降级: %s", e)

    try:
        await collaboration_service.init_redis()
        logger.info("协同编辑服务已初始化")
    except Exception as e:
        logger.warning("协同编辑服务初始化失败: %s", e)

    if TEMPORAL_AVAILABLE:
        try:
            await temporal_service.init_client()
            logger.info("Temporal 工作流服务已初始化")
        except Exception as e:
            logger.warning("Temporal 工作流服务初始化失败: %s", e)

    try:
        from backend.services.style_transfer_service import StyleTransferService
        sts = StyleTransferService()
        await sts._discover_model()
        logger.info("风格迁移模型缓存已初始化")
    except Exception as e:
        logger.warning("风格迁移模型缓存初始化失败: %s", e)

    yield

    try:
        neo4j_service.close()
    except Exception:
        pass
    try:
        qdrant_service.close()
    except Exception:
        pass
    try:
        await collaboration_service.close()
    except Exception:
        pass
    if TEMPORAL_AVAILABLE:
        try:
            await temporal_service.close()
        except Exception:
            pass


app = FastAPI(
    title="NovelCraft API",
    description="AI 小说工坊 - 多智能体协同创作平台",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(outlines.router)
app.include_router(writing.router)
app.include_router(characters.router)
app.include_router(style_transfer.router)
app.include_router(collaboration.router)

# 工作流路由（仅在 Temporal 可用时注册）
if TEMPORAL_AVAILABLE:
    app.include_router(workflows.router)


@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "version": "2.0.0",
        "services": {
            "database": settings.db_driver,
            "neo4j": neo4j_service.available,
            "qdrant": qdrant_service.available,
            "redis": collaboration_service.redis is not None,
            "temporal": TEMPORAL_AVAILABLE and temporal_service.client is not None,
        },
        "features": {
            "style_transfer": True,
            "collaboration": True,
            "workflows": True,
        },
    }
