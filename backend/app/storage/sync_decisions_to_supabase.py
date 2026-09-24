"""Import dataset/Decisions/decisions.csv and dataset/Outcome/outcomes.csv into
the `decisions` / `outcomes` Supabase tables, computing an all-MiniLM-L6-v2
embedding for each decision in the same pass.

Requires SUPABASE_KEY in backend/.env to be a service_role key — RLS on
both tables only allows inserts/upserts from service_role (see
backend/sql/001_setup.sql).

Usage:
  cd MARS/backend
  python -m app.storage.sync_decisions_to_supabase
"""

import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

from app.services.supabase_client import get_supabase_client
from app.storage.embedder import get_embeddings

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_decisions")

# backend/app/storage/sync_decisions_to_supabase.py -> repo root / dataset
DATASET_DIR = Path(__file__).resolve().parent.parent.parent.parent / "dataset"
BATCH_SIZE = 100


def build_embedding_doc(row: Dict[str, Any]) -> str:
    """Build embedding text strictly from decision-time facts (no outcome leakage)."""
    parts = [
        f"Decision Title: {row.get('decision_title', '')}",
        f"Description: {row.get('decision_description', '')}",
        f"Documented Action: {row.get('documented_action', '')}",
        f"Action Type: {row.get('action_type', '')}",
        f"Rationale: {row.get('decision_rationale', '')}",
        f"Department: {row.get('department', '')}",
    ]
    cross_dept = row.get("cross_dept_impact")
    if cross_dept and str(cross_dept).strip() not in ("", "None", "nan"):
        parts.append(f"Cross-Department Impact: {cross_dept}")
    conflicts = row.get("conflicting_perspectives")
    if conflicts and str(conflicts).strip() not in ("", "None", "nan"):
        parts.append(f"Conflicting Perspectives: {conflicts}")
    signals = row.get("quantitative_signals")
    if signals and str(signals).strip() not in ("", "[]", "{}", "None", "nan"):
        parts.append(f"Quantitative Signals: {signals}")

    return "\n".join(parts)


def _clean_decision_row(rec: Dict[str, Any]) -> Dict[str, Any]:
    if rec.get("action_type") == "terminate":
        rec["action_type"] = "reduce"

    # Parse quantitative_signals if stringified JSON
    q_sig = rec.get("quantitative_signals")
    if isinstance(q_sig, str) and (q_sig.startswith("[") or q_sig.startswith("{")):
        try:
            rec["quantitative_signals"] = json.loads(q_sig)
        except Exception:
            rec["quantitative_signals"] = []
    elif not q_sig or q_sig == "None":
        rec["quantitative_signals"] = []

    # Parse tags (Postgres array literal, JSON array, or comma-separated string)
    tags = rec.get("tags")
    if isinstance(tags, str):
        if tags.startswith("{") and tags.endswith("}"):
            rec["tags"] = [t.strip() for t in tags[1:-1].split(",") if t.strip()]
        elif tags.startswith("[") and tags.endswith("]"):
            try:
                rec["tags"] = json.loads(tags)
            except Exception:
                rec["tags"] = []
        elif "," in tags:
            rec["tags"] = [t.strip() for t in tags.split(",") if t.strip()]
        elif tags.strip():
            rec["tags"] = [tags.strip()]
        else:
            rec["tags"] = []
    elif not isinstance(tags, list):
        rec["tags"] = []

    return rec


def sync_decisions(supabase, decisions: List[Dict[str, Any]]):
    logger.info("Checking 'decisions' table in Supabase...")
    try:
        supabase.table("decisions").select("case_id").limit(1).execute()
    except Exception:
        logger.error(
            "\n" + "=" * 80 + "\n"
            "ERROR: Table 'decisions' does not exist in Supabase!\n\n"
            "HOW TO FIX:\n"
            "1. Open Supabase Dashboard -> SQL Editor\n"
            "2. Paste and run backend/sql/005_decisions_outcomes_setup.sql\n"
            "3. Re-run this script!\n"
            "=" * 80
        )
        sys.exit(1)

    total = len(decisions)
    logger.info(f"Computing embeddings for {total} decision cases...")

    docs = [build_embedding_doc(row) for row in decisions]
    embeddings = get_embeddings(docs)
    logger.info(f"Successfully generated {len(embeddings)} normalized 384-d embeddings.")

    records = []
    for row, emb in zip(decisions, embeddings):
        rec = _clean_decision_row(dict(row))
        rec["embedding"] = emb
        records.append(rec)

    logger.info(f"Upserting {total} decisions into 'decisions'...")
    for i in range(0, total, BATCH_SIZE):
        batch = records[i : i + BATCH_SIZE]
        supabase.table("decisions").upsert(batch).execute()
        logger.info(f"  Upserted {min(i + BATCH_SIZE, total)}/{total} decisions...")

    logger.info("Decisions sync completed successfully.")


def sync_outcomes(supabase, outcomes: List[Dict[str, Any]]):
    logger.info("Checking 'outcomes' table in Supabase...")
    try:
        supabase.table("outcomes").select("case_id").limit(1).execute()
    except Exception:
        logger.error(
            "\n" + "=" * 80 + "\n"
            "ERROR: Table 'outcomes' does not exist in Supabase!\n"
            "Run backend/sql/005_decisions_outcomes_setup.sql in the Supabase SQL Editor first.\n"
            "=" * 80
        )
        sys.exit(1)

    total = len(outcomes)
    logger.info(f"Upserting {total} outcomes into 'outcomes'...")
    for i in range(0, total, BATCH_SIZE):
        batch = outcomes[i : i + BATCH_SIZE]
        supabase.table("outcomes").upsert(batch).execute()
        logger.info(f"  Upserted {min(i + BATCH_SIZE, total)}/{total} outcomes...")

    logger.info("Outcomes sync completed successfully.")


def main():
    decisions_path = DATASET_DIR / "Decisions" / "decisions.csv"
    outcomes_path = DATASET_DIR / "Outcome" / "outcomes.csv"

    if not decisions_path.exists() or not outcomes_path.exists():
        logger.error(f"Datasets not found at {decisions_path} or {outcomes_path}")
        return

    with open(decisions_path, "r", encoding="utf-8") as f:
        decisions = list(csv.DictReader(f))

    with open(outcomes_path, "r", encoding="utf-8") as f:
        outcomes = list(csv.DictReader(f))

    logger.info(f"Loaded {len(decisions)} decisions and {len(outcomes)} outcomes from CSV.")

    supabase = get_supabase_client()
    # Decisions first -- outcomes.case_id has a foreign key into decisions.
    sync_decisions(supabase, decisions)
    sync_outcomes(supabase, outcomes)
    logger.info("ALL DATA SYNCED TO SUPABASE SUCCESSFULLY.")


if __name__ == "__main__":
    main()
