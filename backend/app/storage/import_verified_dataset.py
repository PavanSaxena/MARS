"""Upload verified_decisions.csv and verified_outcomes.csv directly to Supabase via Python client.

Usage:
  # From MARS/backend:
  python -m app.storage.import_verified_dataset
"""

import csv
import json
from pathlib import Path
from typing import List, Dict

from app.services.supabase_client import get_supabase_client

DATASET_DIR = Path(__file__).resolve().parent.parent.parent.parent / "Dataset"
BATCH_SIZE = 100


def import_decisions(supabase):
    decisions_file = DATASET_DIR / "verified_decisions.csv"
    if not decisions_file.exists():
        print(f"File not found: {decisions_file}")
        return

    with open(decisions_file, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Importing {len(rows)} verified decisions into Supabase...")

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        cleaned_batch = []
        for r in batch:
            # Parse quantitative_signals JSON string into actual python list/dict
            q_sig = r.get("quantitative_signals")
            if isinstance(q_sig, str) and q_sig.startswith("["):
                try:
                    r["quantitative_signals"] = json.loads(q_sig)
                except Exception:
                    r["quantitative_signals"] = []

            # Format PostgreSQL array literal {a,b} into python list
            tags = r.get("tags", "")
            if isinstance(tags, str) and tags.startswith("{") and tags.endswith("}"):
                r["tags"] = [t.strip() for t in tags[1:-1].split(",") if t.strip()]

            cleaned_batch.append(r)

        supabase.table("verified_decisions").upsert(cleaned_batch).execute()
        print(f"  Inserted {min(i + BATCH_SIZE, len(rows))}/{len(rows)} decisions...")

    print("Decisions import complete.")


def import_outcomes(supabase):
    outcomes_file = DATASET_DIR / "verified_outcomes.csv"
    if not outcomes_file.exists():
        print(f"File not found: {outcomes_file}")
        return

    with open(outcomes_file, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"Importing {len(rows)} verified outcomes into Supabase...")

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        supabase.table("verified_outcomes").upsert(batch).execute()
        print(f"  Inserted {min(i + BATCH_SIZE, len(rows))}/{len(rows)} outcomes...")

    print("Outcomes import complete.")


def main():
    supabase = get_supabase_client()
    print("Starting direct import to Supabase...")
    # Decisions first to satisfy foreign key constraints
    import_decisions(supabase)
    import_outcomes(supabase)
    print("Direct import finished successfully.")


if __name__ == "__main__":
    main()
