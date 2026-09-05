"""Batch compute and update pgvector embeddings for verified_decisions in Supabase.

Guarantees:
  - Embeddings are generated strictly from decision-time facts:
    (title, description, documented action, action type, rationale, quantitative signals).
  - Strictly NO outcome text is included in the embedding text to prevent future leakage.
"""

from app.services.supabase_client import get_supabase_client
from app.storage.embedder import get_embeddings

_FETCH_PAGE_SIZE = 1000
_BATCH_SIZE = 100


def _fetch_all_verified_cases(supabase) -> list:
    """Fetch all rows from verified_decisions with pagination."""
    cases = []
    start = 0

    while True:
        end = start + _FETCH_PAGE_SIZE - 1
        page = supabase.table("verified_decisions").select("*").range(start, end).execute().data
        if not page:
            break

        cases.extend(page)
        if len(page) < _FETCH_PAGE_SIZE:
            break
        start += _FETCH_PAGE_SIZE

    return cases


def _build_decision_doc(case: dict) -> str:
    """Construct document for embedding strictly from decision-time facts."""
    return (
        f"Decision Title: {case.get('decision_title', '')}\n"
        f"Scope: {case.get('decision_description', '')}\n"
        f"Documented Action: {case.get('documented_action', '')}\n"
        f"Action Type: {case.get('action_type', '')}\n"
        f"Rationale: {case.get('decision_rationale', '')}\n"
        f"Quantitative Signals: {case.get('quantitative_signals', '')}\n"
        f"Department: {case.get('department', '')}"
    )


def index_verified_cases():
    """
    Compute and store embeddings directly on verified_decisions table in Supabase.
    Requires supabase_fresh_setup.sql / 003_verified_corpus_setup.sql to have been run first.
    """
    supabase = get_supabase_client()
    cases = _fetch_all_verified_cases(supabase)
    total = len(cases)
    print(f"Fetched {total} verified cases from Supabase.")

    if total == 0:
        print("No cases found in verified_decisions. Have you imported verified_decisions.csv?")
        return

    updated = 0
    for batch_start in range(0, total, _BATCH_SIZE):
        batch = cases[batch_start : batch_start + _BATCH_SIZE]
        docs = [_build_decision_doc(case) for case in batch]
        embeddings = get_embeddings(docs)

        records = [
            {"case_id": case["case_id"], "embedding": embedding}
            for case, embedding in zip(batch, embeddings)
        ]

        supabase.rpc("bulk_update_verified_case_embeddings", {"rows": records}).execute()
        updated += len(records)
        print(f"  Embedded {updated}/{total} verified case(s)...")

    print(f"Successfully updated embeddings for {updated} verified case(s) in Supabase.")


if __name__ == "__main__":
    index_verified_cases()
