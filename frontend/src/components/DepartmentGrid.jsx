import { DEPARTMENTS, parseExplainability } from "../departments.js";

/**
 * status: "idle" | "thinking" | "done"
 * The backend answers all four departments in one round trip (no
 * per-department streaming), so every card transitions together — this
 * reflects that honestly rather than faking staggered progress.
 */
export default function DepartmentGrid({ status, result }) {
  const explainByDept = result ? parseExplainability(result.explainability) : {};

  return (
    <div className="dept-grid">
      {DEPARTMENTS.map((dept) => {
        const hasOutput = Boolean(explainByDept[dept.key]);
        const lightState = status === "thinking" ? "thinking" : hasOutput ? "done" : "idle";
        const statusLabel =
          status === "thinking" ? "processing" : hasOutput ? "reported" : "standing by";

        return (
          <div key={dept.key} className="dept-card" style={{ "--dept-color": dept.color }}>
            <div className="dept-card-head">
              <span className="dept-name">{dept.label}</span>
              <span className={`status-light ${lightState}`} aria-hidden="true" />
            </div>
            <div className="dept-status-label">{statusLabel}</div>
            {hasOutput && (
              <p className="dept-summary">
                {truncate(explainByDept[dept.key], 140)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

// This is a truncated snippet, not full markdown — parsing it as markdown
// risks cutting a "**" pair in half and rendering it wrong. Instead just
// strip the common markers so raw asterisks/#/backticks don't show up.
function truncate(text, max) {
  const flat = text
    .replace(/[*_`#>]+/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return flat.length > max ? `${flat.slice(0, max).trim()}…` : flat;
}
