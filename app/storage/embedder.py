from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")


def get_embedding(text: str) -> list:
    """Return a normalized embedding vector for the given text."""
    return _model.encode(text, normalize_embeddings=True).tolist()
