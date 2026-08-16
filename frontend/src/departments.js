// Names must match aggregator.py's department labels exactly — that's what
// the "[Name]" markers in the explainability string are built from
// (see app/reasoning/aggregator.py: _fmt_department / explainability_lines).
export const DEPARTMENTS = [
  { key: "Finance", label: "Finance", color: "var(--dept-finance)" },
  { key: "R&D", label: "R&D", color: "var(--dept-rd)" },
  { key: "Legal", label: "Legal", color: "var(--dept-legal)" },
  { key: "Operations", label: "Operations", color: "var(--dept-operations)" },
];

/**
 * Split the backend's `explainability` string into { "Finance": "...", ... }
 * blocks. Backend joins per-department blocks as "[Name]\n<text>" separated
 * by blank lines — see aggregator.py's explainability_block.
 */
export function parseExplainability(text) {
  if (!text) return {};
  const blocks = {};
  const parts = text.split(/\n\n(?=\[)/g);
  for (const part of parts) {
    const match = part.match(/^\[(.+?)\]\n([\s\S]*)$/);
    if (match) {
      blocks[match[1].trim()] = match[2].trim();
    }
  }
  return blocks;
}

export function riskBadgeClass(riskLevel) {
  const normalized = (riskLevel || "").toLowerCase();
  if (normalized.includes("high")) return "badge risk-high";
  if (normalized.includes("medium") || normalized.includes("moderate")) return "badge risk-medium";
  if (normalized.includes("low")) return "badge risk-low";
  return "badge";
}
