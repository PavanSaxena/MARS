from .chroma_client import collection
from .embedder import embed

def retrieve_cases(query: str, k: int = 5):

    vector = embed(query)

    results = collection.query(
        query_embeddings=[vector],
        n_results=k
    )

    return results