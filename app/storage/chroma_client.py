import chromadb


def get_collection(collection_name: str = "mars_cases"):
    """Connect to ChromaDB via HTTP server."""
    client = chromadb.HttpClient(host="localhost", port=8001)
    return client.get_or_create_collection(name=collection_name)
