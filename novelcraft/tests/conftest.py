"""
pytest 配置与共享 fixtures — NovelCraft 测试套件

提供测试数据库引擎、会话、HTTP 客户端和示例数据 fixtures。
"""
import os
import sys
import pytest
from typing import Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from backend.main import app
from backend.models.database import Base, get_db
from backend.config import get_settings

settings = get_settings()

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    """使用 asyncio 后端运行异步测试"""
    return "asyncio"


@pytest.fixture(scope="function")
async def test_db_engine():
    """创建测试数据库引擎（内存 SQLite）"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db_session(test_db_engine) -> Generator[AsyncSession, None, None]:
    """创建测试数据库会话"""
    async_session = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    async with async_session() as session:
        yield session


@pytest.fixture(scope="function")
async def client(test_db_session) -> Generator[AsyncClient, None, None]:
    """创建测试 HTTP 客户端（注入测试数据库依赖）"""

    async def override_get_db():
        yield test_db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def sample_project_data():
    """项目示例数据（用于测试）"""
    return {
        "title": "测试小说",
        "synopsis": "这是一个测试小说的梗概，讲述了一个年轻人的冒险故事。",
        "genre": "玄幻",
        "style": "古龙风"
    }


@pytest.fixture
def sample_outline_data():
    """大纲示例数据（用于测试）"""
    return {
        "title": "第一章：初入江湖",
        "content": "主角离开家乡，开始了他的冒险之旅。",
        "node_type": "chapter",
        "sort_order": 0,
        "depth": 0
    }


@pytest.fixture
def sample_character_data():
    """人物示例数据（用于测试）"""
    return {
        "name": "张三",
        "alias": "剑客",
        "description": "一个年轻的剑客",
        "personality": "正直、勇敢",
        "background": "出身武林世家",
        "appearance": "身材修长，剑眉星目",
        "abilities": "精通剑法",
        "status": "alive"
    }


@pytest.fixture
def sample_chapter_data():
    """章节示例数据（用于测试）"""
    return {
        "title": "第一章：初入江湖",
        "chapter_number": 1
    }
