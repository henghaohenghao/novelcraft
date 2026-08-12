"""
配置文件扩展 - V2.0 新增配置项
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    # 数据库配置
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "novelcraft"
    db_password: str = "novelcraft123"
    db_name: str = "novelcraft"
    db_driver: str = "postgresql"

    # Neo4j 图数据库
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "12345678"

    # Qdrant 向量数据库
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""

    # Redis (V2.0 新增)
    redis_url: str = "redis://localhost:6379/0"

    # Temporal 工作流 (V2.0 新增)
    temporal_host: str = "localhost:7233"

    # vLLM 推理服务 (V2.0 新增)
    vllm_base_url: str = "http://localhost:8000"

    # LLM API 配置
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_planner_model: str = "gpt-4o"
    llm_writer_model: str = "gpt-4o-mini"
    llm_reviewer_model: str = "gpt-4o-mini"

    # Embedding 模型
    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_model_path: str | None = None
    embedding_device: str = "cpu"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # 应用配置
    secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = True
    max_revision_rounds: int = 3

    # 风格迁移缓存配置 (V2.0 新增)
    style_cache_hot_capacity_mb: float = 2048  # 显存容量
    style_cache_warm_capacity_mb: float = 8192  # 内存容量
    style_preload_list: list[str] = ["gulong", "maboyang", "jinyong"]  # 预加载风格

    # 协同编辑配置 (V2.0 新增)
    collaboration_snapshot_interval: int = 300  # 快照保存间隔（秒）
    collaboration_max_users_per_room: int = 50  # 每个房间最大用户数

    class Config:
        env_file = ".env"
        env_prefix = "NOVELCRAFT_"

    @property
    def database_url(self) -> str:
        if self.db_driver == "sqlite":
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "novelcraft.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            return f"sqlite+aiosqlite:///{db_path}"
        return f"postgresql+asyncpg://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def database_url_sync(self) -> str:
        if self.db_driver == "sqlite":
            db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "novelcraft.db")
            return f"sqlite:///{db_path}"
        return f"postgresql+psycopg2://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
