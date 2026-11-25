from functools import lru_cache

from src import config
from src.utils.embeddings import EmbeddingClient
from src.utils.postgres import PostgresClient


@lru_cache(maxsize=1)
def _reranker():
    from sentence_transformers import CrossEncoder
    return CrossEncoder(config.RERANKER_MODEL)


class Retriever:
    """Busqueda semantica en pgvector + reranking con cross-encoder (como en la clase 1.3)."""

    def __init__(self, db: PostgresClient | None = None, embedder: EmbeddingClient | None = None,
                 usar_reranker: bool = config.USAR_RERANKER):
        self.db = db or PostgresClient()
        self.embedder = embedder or EmbeddingClient()
        self.usar_reranker = usar_reranker

    def retrieve(self, query: str, top_k: int = config.TOP_K_FINAL) -> list[dict]:
        query_embedding = self.embedder.get_embedding(query)

        # 1. traemos mas candidatos de los que necesitamos
        n_candidatos = config.TOP_K_CANDIDATOS if self.usar_reranker else top_k
        candidatos = self.db.buscar_similares(query_embedding, top_k=n_candidatos)
        if not self.usar_reranker or not candidatos:
            return candidatos[:top_k]

        # 2. el cross-encoder lee pregunta + chunk juntos y los reordena (mas preciso que solo coseno)
        scores = _reranker().predict([(query, c["contenido"]) for c in candidatos])
        for c, s in zip(candidatos, scores):
            c["rerank_score"] = float(s)
        candidatos.sort(key=lambda c: c["rerank_score"], reverse=True)
        return candidatos[:top_k]
