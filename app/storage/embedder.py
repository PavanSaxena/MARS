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
