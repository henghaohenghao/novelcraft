"""
文本嵌入向量服务

使用 sentence-transformers 本地加载嵌入模型，
将文本转换为向量表示，用于 Qdrant 向量检索。
"""
from sentence_transformers import SentenceTransformer
from backend.config import get_settings

settings = get_settings()


class EmbeddingService:
    """嵌入向量服务：文本 -> 向量编码"""

    def __init__(self):
        self._model: SentenceTransformer | None = None

    @property
    def model(self) -> SentenceTransformer:
        """延迟加载嵌入模型（首次使用时加载）"""
        if self._model is None:
            model_name_or_path = settings.embedding_model_path or settings.embedding_model
            self._model = SentenceTransformer(
                model_name_or_path,
                device=settings.embedding_device,
            )
        return self._model

    def encode(self, texts: list[str]) -> list[list[float]]:
        """批量编码文本为向量"""
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def encode_single(self, text: str) -> list[float]:
        """单条文本编码"""
        return self.encode([text])[0]

    @property
    def dimension(self) -> int:
        """获取嵌入向量的维度"""
        return self.model.get_sentence_embedding_dimension()


embedding_service = EmbeddingService()