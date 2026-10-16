from functools import lru_cache
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(MODEL_NAME)


def embed_documents(texts: list[str]) -> list[list[float]]:
    vectors = _get_model().encode(texts, normalize_embeddings=True)
    return vectors.tolist()

def embed_query(text: str) -> list[float]:
    return embed_documents([QUERY_PREFIX + text])[0]