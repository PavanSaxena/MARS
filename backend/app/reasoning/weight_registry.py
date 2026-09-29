"""Persistent Calibrated Weight Registry & Online Learning Store.

Manages persistent parameter weights for Case-Based Reasoning confidence scoring,
allowing continuous empirical calibration without modifying or fine-tuning the LLM.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("app.weights")

REGISTRY_PATH = Path(__file__).resolve().parent / "calibrated_weights_registry.json"

DEFAULT_REGISTRY: Dict[str, Any] = {
    "version": "1.0.0",
    "updated_at": "2026-09-28T00:00:00Z",
    "global_default": [0.45, 0.20, 0.35],
    "departments": {
        "legal": [0.35, 0.40, 0.25],
        "rd": [0.55, 0.20, 0.25],
        "finance": [0.40, 0.15, 0.45],
        "operations": [0.45, 0.25, 0.30],
    },
    "action_types": {
        "expand": [0.40, 0.15, 0.45],
        "terminate": [0.35, 0.20, 0.45],
        "reduce": [0.40, 0.20, 0.40],
        "investigate": [0.50, 0.30, 0.20],
        "defer": [0.40, 0.40, 0.20],
        "approve": [0.40, 0.20, 0.40],
        "revise": [0.50, 0.25, 0.25],
    },
}


class WeightRegistry:
    """Thread-safe persistent storage and continuous calibration manager for decision weights."""

    def __init__(self, registry_file: Path = REGISTRY_PATH):
        self.file_path = registry_file
        self.registry = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to read {self.file_path}: {e}. Initializing default registry.")
        # Create default file
        self._save(DEFAULT_REGISTRY)
        return dict(DEFAULT_REGISTRY)

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist weights to {self.file_path}: {e}")

    def get_weights(
        self,
        department: Optional[str] = None,
        action_type: Optional[str] = None,
    ) -> Tuple[float, float, float]:
        """Fetch calibrated weights for a given department or action profile."""
        dept_key = (department or "").lower().strip()
        act_key = (action_type or "").lower().strip()

        depts = self.registry.get("departments", {})
        actions = self.registry.get("action_types", {})

        if dept_key in depts:
            w = depts[dept_key]
            return (float(w[0]), float(w[1]), float(w[2]))
        if act_key in actions:
            w = actions[act_key]
            return (float(w[0]), float(w[1]), float(w[2]))

        g = self.registry.get("global_default", [0.45, 0.20, 0.35])
        return (float(g[0]), float(g[1]), float(g[2]))

    def update_department_weights(
        self,
        department: str,
        new_weights: Tuple[float, float, float],
    ) -> None:
        """Persist newly calibrated weights for a specific department."""
        dept_key = department.lower().strip()
        if "departments" not in self.registry:
            self.registry["departments"] = {}

        w1, w2, w3 = new_weights
        total = w1 + w2 + w3
        normalized = [round(w1 / total, 3), round(w2 / total, 3), round(w3 / total, 3)]

        self.registry["departments"][dept_key] = normalized
        import datetime
        self.registry["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self._save(self.registry)
        logger.info(f"Updated and persisted calibrated weights for '{dept_key}': {normalized}")


# Singleton instance
weight_registry = WeightRegistry()
