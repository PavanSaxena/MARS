from app.infrastructure.chroma_store.retriever import retrieve_cases


def get_similar_cases(query: str, domain: str | None = None, k: int = 5):
    """Retrieve similar cases for a query; domain filter is reserved for future use."""
    _ = domain
    return retrieve_cases(query=query, k=k)


class CaseRetrievalService:

    def retrieve(self, query: str):

        cases = retrieve_cases(query)

        return cases