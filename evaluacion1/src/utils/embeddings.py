from functools import lru_cache
from src import config


@lru_cache(maxsize=1)
def _modelo():
    # import aca adentro porque sentence-transformers se demora en cargar (torch)
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(config.EMBEDDING_MODEL)


class EmbeddingClient:
    """Embeddings locales con sentence-transformers (384 dimensiones)."""

    def get_embedding(self, text: str) -> list[float]:
        return _modelo().encode(text).tolist()

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        return _modelo().encode(texts, batch_size=32, show_progress_bar=len(texts) > 50).tolist()
