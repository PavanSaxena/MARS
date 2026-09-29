-- Expose the structured outcome label separately from outcome prose so the
-- application can group cases without trying to infer labels from narratives.
-- Apply this migration to existing databases before deploying the matching
-- application code.

drop function if exists match_decisions(vector, int, text, date);

create function match_decisions (
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
  outcome_label text,
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
    coalesce(o.outcome_label, 'unresolved') as outcome_label,
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
