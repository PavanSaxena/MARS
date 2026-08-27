from __future__ import annotations

from app.models.decision_case import DecisionCase, DecisionRow


def validate_row_schema(row: dict) -> DecisionRow:
	try:
		return DecisionCase.model_validate(row)
	except AttributeError:
		return DecisionCase.parse_obj(row)
