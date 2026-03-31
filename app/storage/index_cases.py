import os
from dotenv import load_dotenv
from supabase import create_client

from app.storage.chroma_client import get_collection
from app.storage.embedder import get_embedding

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def index_cases():
    """Fetch all cases from Supabase and index them into ChromaDB."""
    collection = get_collection()

    cases = supabase.table("decision_cases").select("*").execute().data
    print(f"Fetched {len(cases)} cases from Supabase.")

    ids, documents, metadatas, embeddings = [], [], [], []

    for case in cases:
        case_id = str(case["case_id"])

        doc = (
            f"Decision Title: {case['decision_title']}\n"
            f"Trigger: {case['trigger']}\n"
            f"Decision Description: {case['decision_description']}\n"
            f"Options Considered: {case['options_considered']}\n"
            f"Chosen Option: {case['chosen_option']}\n"
            f"Reasoning Summary: {case['reasoning_summary']}\n"
            f"Quantitative Signals: {case['quantitative_signals']}\n"
            f"Risk Level: {case['risk_level']}\n"
            f"Outcome Summary: {case['outcome_summary']}"
        )

        emb = get_embedding(doc)

        metadata = {
            "case_id": case_id,
            "quarter": case.get("quarter", ""),
            "department": case.get("department", ""),
            "risk_level": case.get("risk_level", ""),
            "outcome": case.get("outcome_summary", "unknown"),
        }

        ids.append(case_id)
        documents.append(doc)
        metadatas.append(metadata)
        embeddings.append(emb)

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )

    print(f"✅ Indexed {len(ids)} cases into ChromaDB successfully!")


if __name__ == "__main__":
    index_cases()
