import os
from dotenv import load_dotenv
from supabase import create_client

from chroma_store.chroma_client import get_collection
from chroma_store.embedder import get_embedding


load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def index_cases():
    collection = get_collection()

    # fetch all cases from Supabase
    cases = supabase.table("decision_cases").select("*").execute().data

    print("Fetched cases:", len(cases))

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for case in cases:
        case_id = case["case_id"]

        doc = f"""
        Decision Title: {case['decision_title']}
        Trigger: {case['trigger']}
        Decision Description: {case['decision_description']}
        Options Considered: {case['options_considered']}
        Chosen Option: {case['chosen_option']}
        Reasoning Summary: {case['reasoning_summary']}
        Quantitative Signals: {case['quantitative_signals']}
        Risk Level: {case['risk_level']}
        Outcome Summary: {case['outcome_summary']}
        """

        emb = get_embedding(doc)

        metadata = {
            "case_id": case_id,
            "quarter": case["quarter"],
            "department": case["department"],
            "risk_level": case["risk_level"]
        }

        ids.append(case_id)
        documents.append(doc)
        metadatas.append(metadata)
        embeddings.append(emb)

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    print(f"✅ Indexed {len(ids)} cases into ChromaDB successfully!")


if __name__ == "__main__":
    index_cases()
