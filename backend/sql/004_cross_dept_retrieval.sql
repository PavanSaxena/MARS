-- =============================================================================
-- MIGRATION: Cross-Department Impact & Conflicting Perspectives Retrieval
-- =============================================================================
-- Updates match_decision_cases to:
-- 1. Return cross_dept_impact and conflicting_perspectives columns.
-- 2. Expand department filtering so domain agents retrieve both direct cases
--    (department = filter_department) AND cross-department impacted cases
--    (cross_dept_impact ILIKE '%filter_department%').
-- =============================================================================

-- Ensure columns exist in decision_cases (they already exist in standard schema)
alter table if exists decision_cases 
  add column if not exists cross_dept_impact text;

alter table if exists decision_cases 
  add column if not exists conflicting_perspectives text;

-- Replace match_decision_cases RPC function
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
    case_id::text,
    decision_title,
    decision_description,
    trigger,
    reasoning_summary,
    department,
    cross_dept_impact,
    conflicting_perspectives,
    quarter,
    risk_level,
    outcome_summary,
    1 - (embedding <=> query_embedding) as similarity
  from decision_cases
  where embedding is not null
    and (
      filter_department is null 
      or department = filter_department 
      or (cross_dept_impact is not null and cross_dept_impact ilike ('%' || filter_department || '%'))
    )
  order by embedding <=> query_embedding
  limit match_count;
$$;
