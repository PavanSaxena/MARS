from typing import List

from sentence_transformers import SentenceTransformer

_model = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def get_embedding(text: str) -> list:
    """Return a normalized embedding vector for the given text."""
    return _get_model().encode(text, normalize_embeddings=True).tolist()


def get_embeddings(texts: List[str]) -> List[list]:
    """
    Return normalized embedding vectors for a batch of texts in one call.

    Encoding a list at once lets sentence-transformers batch the forward
    passes on the model, which is far faster than calling get_embedding()
    in a per-item Python loop (see app.storage.index_cases, which used to
    do exactly that and appeared to hang on large tables).
    """
    if not texts:
        return []
    return _get_model().encode(texts, normalize_embeddings=True).tolist()
