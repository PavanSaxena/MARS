-- Run this once in the Supabase SQL editor, after 001_pgvector_setup.sql.
--
-- Backs app/storage/index_cases.py's batched embedding writes. This does a
-- real, set-based UPDATE (never an INSERT), so unlike a naive .upsert(...,
-- on_conflict="case_id") call it can never accidentally create a new row
-- with only case_id + embedding populated and every other NOT NULL column
-- left empty.
create or replace function bulk_update_case_embeddings(rows jsonb)
returns void
language sql
as $$
  update decision_cases
  set embedding = (elem ->> 'embedding')::vector
  from jsonb_array_elements(rows) as elem
  where decision_cases.case_id::text = (elem ->> 'case_id');
$$;
