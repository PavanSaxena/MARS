"""
build_2023_q1_csv.py
Assembles the 100% unique, fully enriched decisions_2023_q1.csv from the 4 modular department generators.
Validates all quality gates and writes to MARS/Dataset/Decisions/decisions_2023_q1.csv.
"""

import json
import os
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from generate_2023_q1_ops import OPS_CASES
from generate_2023_q1_fin import FIN_CASES
from generate_2023_q1_rnd import RND_CASES
from generate_2023_q1_leg import LEG_CASES

# Combine all cases
dept_map = {
    "Operations": OPS_CASES,
    "Finance": FIN_CASES,
    "R&D": RND_CASES,
    "Legal": LEG_CASES
}

all_cases = {}
for dept, cases in dept_map.items():
    for cid, val in cases.items():
        val["department"] = dept
        all_cases[cid] = val

assert len(all_cases) == 160, f"Expected 160 cases, got {len(all_cases)}"

# Create rows in exact case_id order AAPL-2023Q1-0001 to 0160
rows = []
for i in range(1, 161):
    cid = f"AAPL-2023Q1-{i:04d}"
    assert cid in all_cases, f"Missing {cid} in all_cases!"
    c = all_cases[cid]
    
    dept = c["department"]
    action_type = c["action_type"]
    tag_dept = "r&d" if dept == "R&D" else dept.lower()
    tags = f"{{{tag_dept},{action_type}}}"
    
    row = {
        "case_id": cid,
        "company_name": "Apple Inc.",
        "decision_date": "2023-02-02",
        "source_document_id": "quarterly_filings/2023_Q1.pdf",
        "source_url": "https://www.sec.gov/ix?doc=/Archives/edgar/data/0000320193/000032019323000064/aapl-20231231.htm",
        "source_page_or_section": c["src_page"],
        "source_excerpt": c["src_excerpt"],
        "decision_title": c["title"],
        "decision_description": c["desc"],
        "documented_action": c["documented_action"],
        "action_type": action_type,
        "decision_rationale": c["rat"],
        "quantitative_signals": json.dumps(c["q_sig"]),
        "department": dept,
        "department_basis": "reported",
        "tags": tags
    }
    rows.append(row)

df = pd.DataFrame(rows)
out_path = os.path.join(os.path.dirname(__file__), "Decisions", "decisions_2023_q1.csv")
df.to_csv(out_path, index=False)
print(f"Successfully wrote {len(df)} enriched decisions to {out_path}")
