from app.core.config import settings
from app.services.supabase_client import get_supabase_client
from app.storage.embedder import get_embeddings

# PostgREST (and therefore the Supabase client) caps a single select() at
# 1000 rows by default, regardless of how many rows actually exist. Without
# pagination, any table over 1000 rows silently loses its tail: those rows
# never get fetched here, so they never get an embedding written and are
# left with embedding = null (and are then silently excluded from
# match_decision_cases results, per app/storage/retriever.py).
_FETCH_PAGE_SIZE = 1000

# Rows per embed+write batch. Embedding and writing one row at a time (the
# original implementation) meant 1000+ individual model.encode() calls plus
# 1000+ separate network round-trips to Supabase — on a table with over a
# thousand rows this can take many minutes with zero progress output in
# between, which looks identical to the process being hung. Batching both
# steps fixes the actual slowness, and per-batch prints make progress
# visible either way.
_BATCH_SIZE = 100


def _fetch_all_cases(supabase, table: str) -> list:
    """Fetch every row from `table`, paginating past PostgREST's default
    1000-row cap via .range()."""
    cases = []
    start = 0

    while True:
        end = start + _FETCH_PAGE_SIZE - 1
        page = supabase.table(table).select("*").range(start, end).execute().data
        if not page:
            break

        cases.extend(page)
        if len(page) < _FETCH_PAGE_SIZE:
            break
        start += _FETCH_PAGE_SIZE

    return cases


def _build_doc(case: dict) -> str:
    return (
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


def index_cases():
    """
    Compute and store embeddings directly on the `decision_cases` table in
    Supabase (pgvector `embedding` column).

    Requires backend/sql/001_pgvector_setup.sql AND
    backend/sql/002_bulk_update_embeddings.sql to have been run once in
    Supabase first (enables pgvector, adds the embedding column, creates the
    match_decision_cases RPC and the bulk_update_case_embeddings RPC used
    below).

    Run this once, and again any time case rows are added or edited.
    """
    supabase = get_supabase_client()
    table = settings.SUPABASE_CASES_TABLE

    cases = _fetch_all_cases(supabase, table)
    total = len(cases)
    print(f"Fetched {total} cases from Supabase.")

    updated = 0
    for batch_start in range(0, total, _BATCH_SIZE):
        batch = cases[batch_start : batch_start + _BATCH_SIZE]

        docs = [_build_doc(case) for case in batch]
        embeddings = get_embeddings(docs)

        records = [
            {"case_id": case["case_id"], "embedding": embedding}
            for case, embedding in zip(batch, embeddings)
        ]
        # Calls bulk_update_case_embeddings (sql/002_bulk_update_embeddings.sql),
        # which does a real UPDATE ... FROM jsonb_array_elements(...) in one
        # round trip per batch. This can never insert a new row, unlike
        # .upsert(records, on_conflict="case_id"), which falls through to an
        # INSERT whenever a case_id doesn't match an existing row under a
        # real unique constraint — and that INSERT then fails (or silently
        # creates a near-empty row) because only case_id + embedding are
        # populated, violating NOT NULL constraints on every other column.
        supabase.rpc("bulk_update_case_embeddings", {"rows": records}).execute()

        updated += len(records)
        print(f"  Embedded {updated}/{total} case(s)...")

    print(f"Updated embeddings for {updated} case(s) in Supabase.")


if __name__ == "__main__":
    index_cases()
