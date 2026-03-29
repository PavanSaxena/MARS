from typing import Any, Dict


def legal_agent(state: Dict[str, Any]) -> Dict[str, Any]:
	"""Return a placeholder legal output while preserving graph state."""
	return {
		"legal_output": {
			"response": "Legal analysis is not implemented yet.",
			"reasoning": "Placeholder response.",
			"confidence": 0.0,
		},
		"messages": state.get("messages", []),
	}
