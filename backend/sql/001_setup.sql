-- =============================================================================
-- MARS — SUPABASE SETUP (single file, idempotent)
-- =============================================================================
-- Creates the two tables the backend reads and writes, and everything they
-- need: pgvector, indexes, the similarity-search RPC, the batched
-- embedding-write RPC, a corpus-summary RPC, an outcome-chronology trigger,
-- and row-level security.
--
--   decisions  — one row per historical decision (decision-time facts only:
--                 title, description, action taken, rationale, department,
--                 signals). Sourced from dataset/Decisions/decisions.csv.
--
--   outcomes   — one row per decisions.case_id, recording what actually
--                 happened afterward (success/failure/unresolved + the
--                 observed evidence). Sourced from dataset/Outcome/outcomes.csv.
--                 A trigger enforces that an outcome's observation_date is
--                 always after its decision's decision_date.
--
-- Safe to re-run at any time: every statement is CREATE ... IF NOT EXISTS /
-- CREATE OR REPLACE / an idempotent ALTER.
--
-- HOW TO RUN:
--   Supabase Dashboard -> SQL Editor -> paste this whole file -> Run.
--   Then: cd backend && python -m app.storage.sync_decisions_to_supabase
-- =============================================================================

create extension if not exists vector;

-- -----------------------------------------------------------------------------
-- 1. Table: decisions (decision-time facts)
-- -----------------------------------------------------------------------------
create table if not exists decisions (
  case_id text primary key,
  company_name text not null default 'Apple Inc.',
  decision_date date not null,
  source_document_id text,
  source_url text,
  source_page_or_section text,
  source_excerpt text not null,
  decision_title text not null,
  decision_description text not null,
  documented_action text not null,
  action_type text not null check (
    action_type in ('approve', 'expand', 'reduce', 'defer', 'revise', 'investigate', 'reject', 'implement', 'maintain', 'terminate')
  ),
  decision_rationale text,
  quantitative_signals jsonb default '[]'::jsonb,
  department text not null,
  department_basis text not null check (
    department_basis in ('reported', 'inferred')
  ),
  tags text[] default '{}'::text[],
  cross_dept_impact text,
  conflicting_perspectives text,
  embedding vector(384),
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

alter table if exists decisions add column if not exists cross_dept_impact text;
alter table if exists decisions add column if not exists conflicting_perspectives text;
alter table if exists decisions add column if not exists embedding vector(384);

-- Widen action_type to the full set of values present in the dataset
-- (re-running this fixes a table created before 'implement'/'maintain' were added).
alter table if exists decisions drop constraint if exists decisions_action_type_check;
alter table if exists decisions add constraint decisions_action_type_check check (
  action_type in ('approve', 'expand', 'reduce', 'defer', 'revise', 'investigate', 'reject', 'implement', 'maintain', 'terminate')
);

create index if not exists idx_decisions_dept_date
  on decisions (department, decision_date);
create index if not exists idx_decisions_action_type
  on decisions (action_type);

create index if not exists idx_decisions_embedding_hnsw
  on decisions
  using hnsw (embedding vector_cosine_ops);

-- -----------------------------------------------------------------------------
-- 2. Table: outcomes (subsequent, observed outcome per decision)
-- -----------------------------------------------------------------------------
create table if not exists outcomes (
  case_id text primary key references decisions(case_id) on delete cascade,
  outcome_label text not null check (
    outcome_label in ('success', 'failure', 'unresolved')
  ),
  observation_date date not null,
  observation_source_docs text,
  observation_source_section text,
  observation_excerpt text not null,
  created_at timestamptz default now()
);

create index if not exists idx_outcomes_label
  on outcomes (outcome_label);
create index if not exists idx_outcomes_obs_date
  on outcomes (observation_date);

-- -----------------------------------------------------------------------------
-- 3. Trigger: outcome must be observed strictly after its decision
-- -----------------------------------------------------------------------------
create or replace function check_outcome_chronology()
returns trigger
language plpgsql
as $$
declare
  linked_decision_date date;
begin
  select decision_date into linked_decision_date
  from decisions
  where case_id = new.case_id;

  if linked_decision_date is null then
    raise exception 'Integrity Error: Linked case_id "%" does not exist in decisions', new.case_id;
  end if;

  if new.observation_date <= linked_decision_date then
    raise exception 'Chronology Violation: outcome observation_date (%) must be strictly after decision_date (%) for case "%"',
      new.observation_date, linked_decision_date, new.case_id;
  end if;

  return new;
end;
$$;

drop trigger if exists trg_check_outcome_chronology on outcomes;
create trigger trg_check_outcome_chronology
  before insert or update on outcomes
  for each row
  execute function check_outcome_chronology();

-- -----------------------------------------------------------------------------
-- 4. RPC: match_decisions — similarity search the backend calls to retrieve
--    historical precedent for a query (app/storage/retriever.py).
--
--    Joins decisions with outcomes so each result already carries what
--    happened afterward:
--      quarter          <- derived from decision_date, e.g. "2023Q1"
--      trigger           <- source_excerpt (the disclosed context that led to the decision)
--      reasoning_summary <- decision_rationale
--      risk_level        <- action_type (approve/expand/reduce/defer/revise/investigate/reject)
--      outcome_summary   <- outcomes.observation_excerpt, falling back to
--                            outcome_label, or "unresolved" if no outcome
--                            has been recorded yet for that case
-- -----------------------------------------------------------------------------
create or replace function match_decisions (
  query_embedding vector(384),
  match_count int default 5,
  filter_department text default null,
  as_of_date date default null
)
returns table (
  case_id text,
  decision_title text,
  decision_description text,
  trigger text,
  reasoning_summary text,
  department text,
  cross_dept_impact text,
  conflicting_perspectives text,
  quarter text,
  risk_level text,
  outcome_summary text,
  similarity float
)
language sql stable
as $$
  select
    d.case_id,
    d.decision_title,
    d.decision_description,
    d.source_excerpt as trigger,
    d.decision_rationale as reasoning_summary,
    d.department,
    d.cross_dept_impact,
    d.conflicting_perspectives,
    to_char(d.decision_date, 'YYYY"Q"Q') as quarter,
    d.action_type as risk_level,
    coalesce(o.observation_excerpt, o.outcome_label, 'unresolved') as outcome_summary,
    1 - (d.embedding <=> query_embedding) as similarity
  from decisions d
  left join outcomes o on o.case_id = d.case_id
  where d.embedding is not null
    and (as_of_date is null or d.decision_date <= as_of_date)
    and (
      filter_department is null
      or d.department = filter_department
      or (d.cross_dept_impact is not null and d.cross_dept_impact ilike ('%' || filter_department || '%'))
    )
  order by d.embedding <=> query_embedding
  limit match_count;
$$;

-- -----------------------------------------------------------------------------
-- 5. RPC: bulk embedding update for decisions
-- -----------------------------------------------------------------------------
create or replace function bulk_update_decision_embeddings(rows jsonb)
returns void
language sql
as $$
  update decisions
  set embedding = (elem ->> 'embedding')::vector,
      updated_at = now()
  from jsonb_array_elements(rows) as elem
  where decisions.case_id = (elem ->> 'case_id');
$$;

-- -----------------------------------------------------------------------------
-- 6. RPC: dataset summary statistics (sanity-check the import)
-- -----------------------------------------------------------------------------
create or replace function get_decisions_corpus_summary()
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
  select count(*) into total_decisions from decisions;
  select count(*) into total_outcomes from outcomes;
  select count(*) into success_count from outcomes where outcome_label = 'success';
  select count(*) into failure_count from outcomes where outcome_label = 'failure';
  select count(*) into unresolved_count from outcomes where outcome_label = 'unresolved';

  select jsonb_object_agg(department, count) into dept_breakdown
  from (select department, count(*) as count from decisions group by department) d;

  select jsonb_object_agg(action_type, count) into action_breakdown
  from (select action_type, count(*) as count from decisions group by action_type) a;

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
-- 7. RLS: readable by anyone, writable only by the service role
-- -----------------------------------------------------------------------------
alter table decisions enable row level security;
alter table outcomes enable row level security;

do $$
begin
  if not exists (select 1 from pg_policies where tablename = 'decisions' and policyname = 'Allow read on decisions') then
    create policy "Allow read on decisions" on decisions for select using (true);
  end if;

  if not exists (select 1 from pg_policies where tablename = 'outcomes' and policyname = 'Allow read on outcomes') then
    create policy "Allow read on outcomes" on outcomes for select using (true);
  end if;

  if not exists (select 1 from pg_policies where tablename = 'decisions' and policyname = 'Allow all on decisions for service_role') then
    create policy "Allow all on decisions for service_role" on decisions for all using (auth.role() = 'service_role');
  end if;

  if not exists (select 1 from pg_policies where tablename = 'outcomes' and policyname = 'Allow all on outcomes for service_role') then
    create policy "Allow all on outcomes for service_role" on outcomes for all using (auth.role() = 'service_role');
  end if;
end $$;

-- =============================================================================
-- DONE. Next: run app/storage/sync_decisions_to_supabase.py to import and
-- embed dataset/Decisions/decisions.csv and dataset/Outcome/outcomes.csv.
-- =============================================================================
