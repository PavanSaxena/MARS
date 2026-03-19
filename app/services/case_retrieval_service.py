from infrastructure.chroma_store.retriever import retrieve_cases

class CaseRetrievalService:

    def retrieve(self, query: str):

        cases = retrieve_cases(query)

        return cases