import logging
from typing import List

from sentence_transformers import SentenceTransformer

_model = None
logger = logging.getLogger(__name__)


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("embedding_model_loading model=all-MiniLM-L6-v2")
        _model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("embedding_model_ready model=all-MiniLM-L6-v2")
    return _model


def get_embedding(text: str) -> list:
    """Return a normalized embedding vector for the given text."""
    logger.info("embedding_started input_count=1")
    embedding = _get_model().encode(text, normalize_embeddings=True).tolist()
    logger.info("embedding_finished input_count=1 dimensions=%d", len(embedding))
    return embedding


def get_embeddings(texts: List[str]) -> List[list]:
    """
    Return normalized embedding vectors for a batch of texts in one call.

    Encoding a list at once lets sentence-transformers batch the forward
    passes on the model, which is far faster than calling get_embedding()
    in a per-item Python loop (see app.storage.index_cases, which used to
    do exactly that and appeared to hang on large tables).
    """
    if not texts:
        logger.info("embedding_batch_skipped input_count=0")
        return []
    logger.info("embedding_batch_started input_count=%d", len(texts))
    embeddings = _get_model().encode(texts, normalize_embeddings=True).tolist()
    logger.info(
        "embedding_batch_finished input_count=%d dimensions=%d",
        len(embeddings),
        len(embeddings[0]) if embeddings else 0,
    )
    return embeddings
