"""Storage and persistence layer for embeddings and pgvector database."""

from app.storage.embedder import get_embedding, get_embeddings
from app.storage.retriever import retrieve_cases

__all__ = ["get_embedding", "get_embeddings", "retrieve_cases"]
