from pydantic_settings import BaseSettings
from functools import lru_cache
import os


class Settings(BaseSettings):
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "novelcraft"
    db_password: str = "novelcraft123"
    db_name: str = "novelcraft"
    db_driver: str = "postgresql"  # "postgresql" or "sqlite"

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "12345678"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_api_key: str = ""

    redis_url: str = "redis://localhost:6379/0"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_planner_model: str = "gpt-4o"
    llm_writer_model: str = "gpt-4o-mini"
    llm_reviewer_model: str = "gpt-4o-mini"

    embedding_model: str = "BAAI/bge-small-zh-v1.5"
    embedding_model_path: str | None = None
    embedding_device: str = "cpu"

    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    secret_key: str = "dev-secret-key-change-in-production"
    debug: bool = True

    max_revision_rounds: int = 3
    # Human-in-the-Loop：审查未通过时是否暂停等待人工决策
    enable_human_review: bool = True
    # 触发人工审核的修改轮次阈值（已修改次数 >= 该值且审查仍未通过时触发）
    human_review_revision_threshold: int = 1

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