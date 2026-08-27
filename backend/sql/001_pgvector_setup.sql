-- Run this once in the Supabase SQL editor (or via `supabase db execute`).
-- Replaces the ChromaDB vector store with pgvector directly on the
-- `decision_cases` table already used for indexing.

-- 1. Enable pgvector
create extension if not exists vector;

-- 2. Add an embedding column sized for all-MiniLM-L6-v2 (384 dimensions).
--    If you switch embedding models later, this dimension must match.
alter table decision_cases
  add column if not exists embedding vector(384);

-- 3. Index for fast approximate nearest-neighbour search.
--    ivfflat needs the table to have some rows before it's built well;
--    if this is a brand-new table, run ANALYZE / rebuild the index after
--    the first full backfill via index_cases.py.
create index if not exists decision_cases_embedding_idx
  on decision_cases
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

-- 4. Similarity search RPC — called from app/storage/retriever.py via
--    supabase.rpc("match_decision_cases", {...})
create or replace function match_decision_cases (
  query_embedding vector(384),
  match_count int default 5,
  filter_department text default null
)
returns table (
  case_id text,
  decision_title text,
  decision_description text,
  trigger text,
  reasoning_summary text,
  department text,
  quarter text,
  risk_level text,
  outcome_summary text,
  similarity float
)
language sql stable
as $$
  select
    case_id::text,
    decision_title,
    decision_description,
    trigger,
    reasoning_summary,
    department,
    quarter,
    risk_level,
    outcome_summary,
    1 - (embedding <=> query_embedding) as similarity
  from decision_cases
  where embedding is not null
    and (filter_department is null or department = filter_department)
  order by embedding <=> query_embedding
  limit match_count;
$$;
