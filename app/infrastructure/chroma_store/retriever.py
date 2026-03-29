from .chroma_client import get_collection
from .embedder import get_embedding

def retrieve_cases(query: str, k: int = 5):

    collection = get_collection()

    vector = get_embedding(query)

    results = collection.query(
        query_embeddings=[vector],
        n_results=k
    )

    return results