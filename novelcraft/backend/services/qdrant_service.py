"""
Qdrant 向量数据库服务

负责管理项目设定片段和段落嵌入的存储与语义检索，
为写作智能体提供相关上下文。
"""
import uuid
import logging
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from backend.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


class QdrantService:
    """Qdrant 向量数据库客户端"""

    def __init__(self):
        self._client: QdrantClient | None = None
        self._embedding_dim = 512
        self.available: bool = False

    @property
    def client(self) -> QdrantClient:
        """延迟连接 Qdrant 客户端"""
        if self._client is None:
            self._client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                api_key=settings.qdrant_api_key or None,
                timeout=5,
            )
        return self._client

    def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            self._client = None
        self.available = False

    def init_collections(self, embedding_dim: int | None = None):
        """初始化向量集合：创建设定片段、段落嵌入、章节摘要三个 collection"""
        if embedding_dim:
            self._embedding_dim = embedding_dim
        collections = {
            "setting_fragments": "设定片段存储",
            "paragraph_embeddings": "段落嵌入存储",
            "chapter_summaries": "章节摘要向量（分层记忆召回）",
        }
        for name, _ in collections.items():
            if not self.client.collection_exists(name):
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(size=self._embedding_dim, distance=Distance.COSINE),
                )
        self.available = True

    def upsert_setting(self, project_id: str, setting_id: str, text: str, embedding: list[float], metadata: dict = None):
        """插入或更新设定片段向量"""
        if not self.available:
            return
        payload = {
            "project_id": project_id,
            "text": text,
            "setting_id": setting_id,
        }
        if metadata:
            payload.update(metadata)

        self.client.upsert(
            collection_name="setting_fragments",
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload=payload,
                )
            ],
        )

    def upsert_paragraph(self, project_id: str, chapter_id: str, paragraph_index: int, text: str, embedding: list[float]):
        """插入章节段落向量"""
        if not self.available:
            return
        self.client.upsert(
            collection_name="paragraph_embeddings",
            points=[
                PointStruct(
                    id=str(uuid.uuid4()),
                    vector=embedding,
                    payload={
                        "project_id": project_id,
                        "chapter_id": chapter_id,
                        "paragraph_index": paragraph_index,
                        "text": text,
                    },
                )
            ],
        )

    def search_settings(self, project_id: str, query_embedding: list[float], limit: int = 5) -> list[dict]:
        """语义搜索：查找与查询最相关的设定片段"""
        if not self.available:
            return []
        results = self.client.query_points(
            collection_name="setting_fragments",
            query=query_embedding,
            query_filter=Filter(
                must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
            ),
            limit=limit,
        ).points
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "setting_id": hit.payload.get("setting_id", ""),
            }
            for hit in results
        ]

    def search_settings_by_keyword(self, project_id: str, keyword: str, limit: int = 5) -> list[dict]:
        """基于关键词的设定搜索（自动生成 embedding）"""
        if not self.available:
            return []
        try:
            from backend.services.embedding_service import embedding_service
            query_embedding = embedding_service.encode_single(keyword)
            return self.search_settings(project_id, query_embedding, limit)
        except Exception as e:
            logger.warning(f"关键词搜索设定失败: {e}")
            return []

    def search_style_guide_by_keyword(self, project_id: str, style_name: str, limit: int = 5) -> list[dict]:
        """基于关键词的风格指南搜索"""
        if not self.available:
            return []
        try:
            from backend.services.embedding_service import embedding_service
            query_embedding = embedding_service.encode_single(f"写作风格 {style_name}")
            return self.search_settings(project_id, query_embedding, limit)
        except Exception as e:
            logger.warning(f"关键词搜索风格指南失败: {e}")
            return []

    def search_paragraphs(self, project_id: str, query_embedding: list[float], limit: int = 5) -> list[dict]:
        """语义搜索：查找最相关的段落"""
        if not self.available:
            return []
        results = self.client.query_points(
            collection_name="paragraph_embeddings",
            query=query_embedding,
            query_filter=Filter(
                must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
            ),
            limit=limit,
        ).points
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "chapter_id": hit.payload.get("chapter_id", ""),
                "paragraph_index": hit.payload.get("paragraph_index", 0),
            }
            for hit in results
        ]

    def upsert_summary(
        self,
        project_id: str,
        chapter_id: str,
        chapter_number: int,
        text: str,
        embedding: list[float],
        importance_score: float = 0.5,
    ) -> str:
        """插入或更新章节摘要向量（分层记忆召回用）"""
        if not self.available:
            logger.info(f"[Qdrant] upsert_summary 跳过 ch{chapter_number}（服务不可用）")
            return ""
        point_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name="chapter_summaries",
            points=[
                PointStruct(
                    id=point_id,
                    vector=embedding,
                    payload={
                        "project_id": project_id,
                        "chapter_id": chapter_id,
                        "chapter_number": chapter_number,
                        "text": text,
                        "importance_score": importance_score,
                    },
                )
            ],
        )
        logger.info(
            f"[Qdrant] upsert_summary 完成 ch{chapter_number} | "
            f"point_id={point_id} 向量维度={len(embedding)} importance={importance_score}"
        )
        return point_id

    def search_summaries(
        self, project_id: str, query_embedding: list[float], limit: int = 5
    ) -> list[dict]:
        """语义搜索：召回与查询最相关的章节摘要（突破时序限制）"""
        if not self.available:
            logger.info(f"[Qdrant] search_summaries 跳过（服务不可用）")
            return []
        results = self.client.query_points(
            collection_name="chapter_summaries",
            query=query_embedding,
            query_filter=Filter(
                must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
            ),
            limit=limit,
        ).points
        logger.info(
            f"[Qdrant] search_summaries 完成 project={project_id} | "
            f"召回{len(results)}条 scores={[round(h.score, 3) for h in results]}"
        )
        return [
            {
                "id": hit.id,
                "score": hit.score,
                "text": hit.payload.get("text", ""),
                "chapter_id": hit.payload.get("chapter_id", ""),
                "chapter_number": hit.payload.get("chapter_number", 0),
                "importance_score": hit.payload.get("importance_score", 0.5),
            }
            for hit in results
        ]

    def delete_project_data(self, project_id: str):
        """删除项目相关所有向量数据"""
        if not self.available:
            return
        for collection in ["setting_fragments", "paragraph_embeddings", "chapter_summaries"]:
            self.client.delete(
                collection_name=collection,
                points_selector=Filter(
                    must=[FieldCondition(key="project_id", match=MatchValue(value=project_id))]
                ),
            )


qdrant_service = QdrantService()
