from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.models.decision_case import DecisionCase


CSV_COLUMNS = list(DecisionCase.model_fields)


def export_csv(rows: list[dict], path: str | Path) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame = frame.reindex(columns=CSV_COLUMNS)
    frame.to_csv(output_path, index=False)