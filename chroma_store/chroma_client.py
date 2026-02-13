import chromadb

def get_collection():
    client = chromadb.PersistentClient(path="chromadb/chroma_db")
    collection = client.get_or_create_collection(name="mars_cases")
    return collection
