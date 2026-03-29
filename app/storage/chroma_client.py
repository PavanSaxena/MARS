import chromadb
from pathlib import Path

# Resolve DB path relative to the project root regardless of where the script is run
DB_PATH = str(Path(__file__).resolve().parents[4] / "chromadb" / "chroma_db")


def get_collection(collection_name: str = "mars_cases"):
    """Return (or create) the named ChromaDB collection."""
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(name=collection_name)
