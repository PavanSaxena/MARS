# MARS Evaluation v2

This package is the leakage-safe research evaluation layer for MARS. It does
not replace the runtime system; it replaces the earlier research harnesses that
allowed self-retrieval, simulated statistics, or future outcome exposure.

Core rules:

1. Split by `decision_date`, never by random row sampling.
2. Retrieval for a replay case must exclude the target `case_id`.
3. Retrieval must exclude decisions with `decision_date >= query decision_date`.
4. Outcome text/labels may be used only when `observation_date <= query decision_date`.
5. Paper tables must be generated from real per-case outputs, not simulated arrays.

Initial manifest:

```bash
python3 -m evaluation_v2.build_manifests
```

Quick combined audit:

```bash
backend/.venv/bin/python -m evaluation_v2.research_audit
```

Protocol tests:

```bash
backend/.venv/bin/pytest -q evaluation_v2/test_protocol.py evaluation_v2/test_tool_robustness.py
```

See `EXPERIMENT_PLAN.md` for the paper-oriented experiment matrix and
acceptance criteria.

Replay outputs and trace smoke test:

```bash
backend/.venv/bin/python -m evaluation_v2.run_replay_outputs --split validation --max-cases 25
```
