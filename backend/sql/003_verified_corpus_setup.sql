-- =============================================================================
-- SUPABASE SETUP: MARS VERIFIED DATASET & CONTRACTS (CLEAN & NON-DESTRUCTIVE)
-- Reference: MARS_DATA_AND_SUCCESS_PLAN.md (Phases 1 & 3)
-- =============================================================================
-- NOTE:
--   - This script is 100% additive and NON-DESTRUCTIVE.
--   - Existing tables (including `decision_cases`) are PRESERVED and NOT DROPPED.
--   - Excludes all reviewer/annotator IDs and legacy audit tables.
--   - Strictly enforces separation between decision-time facts and subsequent outcomes.
--   - Strictly enforces time sequencing: outcome observation_date > decision_date.
--   - Provides pgvector HNSW indexing and time-safe similarity retrieval RPC.
--
-- HOW TO RUN:
-- Open your Supabase Dashboard -> SQL Editor -> Paste this entire file -> Click Run.
-- =============================================================================

-- 1. Enable pgvector extension
create extension if not exists vector;

-- -----------------------------------------------------------------------------
-- 2. Table: verified_decisions (Decision-Time Corpus)
-- -----------------------------------------------------------------------------
-- Contains facts known AT DECISION TIME only.
-- Strictly excludes: outcomes, agent confidences, master decisions, synthetic options.
create table if not exists verified_decisions (
  case_id text primary key,
  company_name text not null,
  decision_date date not null,
  source_document_id text,
  source_url text not null,
  source_page_or_section text not null,
  source_excerpt text not null,
  decision_title text not null,
  decision_description text not null,
  documented_action text not null,
  action_type text not null check (
    action_type in ('approve', 'expand', 'reduce', 'defer', 'revise', 'investigate', 'reject')
  ),
  decision_rationale text,
  quantitative_signals jsonb default '[]'::jsonb,
  department text not null,
  department_basis text not null check (
    department_basis in ('reported', 'inferred')
  ),
  tags text[] default '{}'::text[],
  embedding vector(384),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

-- B-Tree indexes for fast filtered lookups
create index if not exists idx_verified_decisions_dept_date 
  on verified_decisions (department, decision_date);
create index if not exists idx_verified_decisions_action_type 
  on verified_decisions (action_type);

-- Vector Index using HNSW for fast cosine distance similarity
create index if not exists idx_verified_decisions_embedding_hnsw
  on verified_decisions
  using hnsw (embedding vector_cosine_ops);

-- -----------------------------------------------------------------------------
-- 3. Table: verified_outcomes (Subsequent Outcome Corpus)
-- -----------------------------------------------------------------------------
-- Stores subsequent empirical results strictly separated from decision retrieval.
create table if not exists verified_outcomes (
  outcome_id text primary key,
  case_id text not null references verified_decisions(case_id) on delete cascade,
  observation_date date not null,
  source_document_id text,
  source_url text not null,
  source_page_or_section text not null,
  source_excerpt text not null,
  success_criterion text not null,
  success_time_window text not null,
  observed_result text not null,
  outcome_label text not null check (
    outcome_label in ('success', 'failure', 'unresolved')
  ),
  created_at timestamptz default now()
);

create index if not exists idx_verified_outcomes_case_id
  on verified_outcomes (case_id);
create index if not exists idx_verified_outcomes_label
  on verified_outcomes (outcome_label);
create index if not exists idx_verified_outcomes_obs_date
  on verified_outcomes (observation_date);

-- -----------------------------------------------------------------------------
-- 4. Trigger: Enforce Strict Time Sequencing on Outcomes
-- -----------------------------------------------------------------------------
create or replace function check_verified_outcome_chronology()
returns trigger
language plpgsql
as $$
declare
  linked_decision_date date;
begin
  -- Retrieve decision_date of linked decision
  select decision_date into linked_decision_date
  from verified_decisions
  where case_id = new.case_id;

  if linked_decision_date is null then
    raise exception 'Integrity Error: Linked case_id "%" does not exist in verified_decisions', new.case_id;
  end if;

  -- Chronological rule: outcome observation must occur strictly AFTER decision date
  if new.observation_date <= linked_decision_date then
    raise exception 'Chronology Violation: Outcome observation_date (%) must be strictly after decision_date (%) for case "%"',
      new.observation_date, linked_decision_date, new.case_id;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_check_verified_outcome_chronology on verified_outcomes;
create trigger trg_check_verified_outcome_chronology
  before insert or update on verified_outcomes
  for each row
  execute function check_verified_outcome_chronology();

-- -----------------------------------------------------------------------------
-- 5. RPC: Time-Safe Similarity Search (Historical Replay & Benchmark)
-- -----------------------------------------------------------------------------
-- Guarantees:
--   - Only searches decision facts (no outcome text in embeddings or return values)
--   - Strict time cutoff: excludes decisions made after as_of_date
create or replace function match_verified_decisions (
  query_embedding vector(384),
  as_of_date date default null,
  match_count int default 5,
  filter_department text default null
)
returns table (
  case_id text,
  company_name text,
  decision_date date,
  source_document_id text,
  source_url text,
  source_page_or_section text,
  source_excerpt text,
  decision_title text,
  decision_description text,
  documented_action text,
  action_type text,
  decision_rationale text,
  quantitative_signals jsonb,
  department text,
  department_basis text,
  tags text[],
  similarity float
)
language sql stable
as $$
  select
    case_id,
    company_name,
    decision_date,
    source_document_id,
    source_url,
    source_page_or_section,
    source_excerpt,
    decision_title,
    decision_description,
    documented_action,
    action_type,
    decision_rationale,
    quantitative_signals,
    department,
    department_basis,
    tags,
    1 - (embedding <=> query_embedding) as similarity
  from verified_decisions
  where embedding is not null
    and (as_of_date is null or decision_date <= as_of_date)
    and (filter_department is null or department = filter_department)
  order by embedding <=> query_embedding
  limit match_count;
$$;

-- -----------------------------------------------------------------------------
-- 6. RPC: Bulk Embedding Update for Verified Decisions
-- -----------------------------------------------------------------------------
create or replace function bulk_update_verified_case_embeddings(rows jsonb)
returns void
language sql
as $$
  update verified_decisions
  set embedding = (elem ->> 'embedding')::vector
  from jsonb_array_elements(rows) as elem
  where verified_decisions.case_id = (elem ->> 'case_id');
$$;

-- -----------------------------------------------------------------------------
-- 7. RPC: Dataset Summary Statistics
-- -----------------------------------------------------------------------------
create or replace function get_verified_corpus_summary()
returns jsonb
language plpgsql stable
as $$
declare
  total_decisions int;
  total_outcomes int;
  success_count int;
  failure_count int;
  unresolved_count int;
  dept_breakdown jsonb;
  action_breakdown jsonb;
begin
  select count(*) into total_decisions from verified_decisions;
  select count(*) into total_outcomes from verified_outcomes;
  select count(*) into success_count from verified_outcomes where outcome_label = 'success';
  select count(*) into failure_count from verified_outcomes where outcome_label = 'failure';
  select count(*) into unresolved_count from verified_outcomes where outcome_label = 'unresolved';

  select jsonb_object_agg(department, count)
  into dept_breakdown
  from (
    select department, count(*) as count
    from verified_decisions
    group by department
  ) d;

  select jsonb_object_agg(action_type, count)
  into action_breakdown
  from (
    select action_type, count(*) as count
    from verified_decisions
    group by action_type
  ) a;

  return jsonb_build_object(
    'total_decisions', total_decisions,
    'total_outcomes', total_outcomes,
    'success_outcomes', success_count,
    'failure_outcomes', failure_count,
    'unresolved_outcomes', unresolved_count,
    'department_breakdown', coalesce(dept_breakdown, '{}'::jsonb),
    'action_type_breakdown', coalesce(action_breakdown, '{}'::jsonb)
  );
end;
$$;

-- -----------------------------------------------------------------------------
-- 8. Security: Enable Row Level Security (RLS)
-- -----------------------------------------------------------------------------
alter table verified_decisions enable row level security;
alter table verified_outcomes enable row level security;

-- Permissive read policy for anonymous & authenticated users
do $$
begin
  if not exists (
    select 1 from pg_policies 
    where tablename = 'verified_decisions' and policyname = 'Allow read on verified_decisions'
  ) then
    create policy "Allow read on verified_decisions"
      on verified_decisions for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies 
    where tablename = 'verified_outcomes' and policyname = 'Allow read on verified_outcomes'
  ) then
    create policy "Allow read on verified_outcomes"
      on verified_outcomes for select using (true);
  end if;

  if not exists (
    select 1 from pg_policies 
    where tablename = 'verified_decisions' and policyname = 'Allow all on verified_decisions for service_role'
  ) then
    create policy "Allow all on verified_decisions for service_role"
      on verified_decisions for all using (auth.role() = 'service_role');
  end if;

  if not exists (
    select 1 from pg_policies 
    where tablename = 'verified_outcomes' and policyname = 'Allow all on verified_outcomes for service_role'
  ) then
    create policy "Allow all on verified_outcomes for service_role"
      on verified_outcomes for all using (auth.role() = 'service_role');
  end if;
end $$;
